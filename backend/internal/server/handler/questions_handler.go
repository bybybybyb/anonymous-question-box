package handler

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/anonymous-question-box/internal/domain/repository"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

type QuestionsHandler struct {
	ProfileManager  repository.ProfileManager
	TokenManager    repository.TokenManager
	QuestionManager repository.QuestionManager
	TempFileRepo    repository.TempFileRepo
	PersistFileRepo repository.PersistFileRepo
	VisitChan       chan *model.VisitStatus
}

// NewQuestionToken returns a new encoded token for identifying & authenticating the submission of a new question
func (q *QuestionsHandler) NewQuestionToken(c *gin.Context) {
	id := c.GetString("uuid")
	if id == "" {
		newUUID, err := uuid.NewRandom()
		if err != nil {
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("UUID生成失败，错误信息：%s，请联系网站管理员", err.Error())})
			return
		}
		id = newUUID.String()
	}
	token, err := q.TokenManager.GenerateToken(c, id)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("token生成失败，错误信息：%s，请联系网站管理员", err.Error())})
		return
	}
	c.JSON(200, struct {
		Token string `json:"token"`
	}{Token: token})
}

// SubmitNewQuestion records a new question submitted as long as it passes all validations
func (q *QuestionsHandler) SubmitNewQuestion(c *gin.Context) {
	body, err := ioutil.ReadAll(c.Request.Body)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法读取投稿请求，错误信息：%s", err.Error())})
		return
	}
	req := &model.Question{
		UUID:    c.GetString("uuid"),
		AskedAt: time.Now(),
	}
	err = json.Unmarshal(body, req)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法解析投稿请求，错误信息：%s", err.Error())})
		return
	}
	runeLimit, ok := q.ProfileManager.GetRuneLimitByOwnerNameAndQuestionType(req.Owner, req.Type)
	if !ok {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("未知提问箱主人 %s 或投稿类型 %s", req.Owner, req.Type)})
		return
	}
	req.Text = strings.TrimSpace(req.Text)
	if int32(utf8.RuneCountInString(req.Text)) > runeLimit {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("投稿长度超过最大限度 %d", runeLimit)})
		return
	} else if int32(utf8.RuneCountInString(req.Text)) == 0 {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: "空投稿"})
		return
	}
	startTime, endTime, ok := q.ProfileManager.GetFlightTimeByOwnerNameAndQuestionType(req.Owner, req.Type)
	if ok {
		now := time.Now()
		if now.Before(startTime) {
			c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("尚未开始接受投稿，投稿将于 %s 开放", startTime.Format(time.RFC3339))})
			return
		}
		if now.After(endTime) {
			c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("投稿已于 %s 截止", endTime.Format(time.RFC3339))})
			return
		}
	}
	if !q.ProfileManager.IsImageSupportedByOwnerNameAndQuestionType(req.Owner, req.Type) && len(req.ImageIDs) > 0 {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: "本提问箱不支持图片上传"})
		return
	} else {
		images := []*model.ImageMetadata{}
		for _, imageID := range req.ImageIDs {
			if tempFilePath, filename := q.TempFileRepo.GetTempFilePathAndNameByID(imageID); tempFilePath != "" {
				key := strings.Join([]string{req.UUID, imageID, filename}, "/")
				err := q.PersistFileRepo.Upload(c, key, tempFilePath)
				if err != nil {
					c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("图片上传失败，错误信息：%s", err.Error())})
					return
				}
				images = append(images, &model.ImageMetadata{QuestionUUID: req.UUID, Key: key})
			}
		}
		statusErr := q.QuestionManager.StoreImageMetadata(c, images)
		if statusErr != nil {
			c.AbortWithStatusJSON(statusErr.Code(), ErrorResp{Error: fmt.Sprintf("图片上传失败，错误信息：%s", statusErr.Error())})
			return
		}
	}
	statusErr := q.QuestionManager.InsertQuestion(c, req)
	if statusErr != nil {
		c.AbortWithStatusJSON(statusErr.Code(), ErrorResp{Error: fmt.Sprintf("提交失败，错误信息：%s，请联系网站管理员", statusErr.Error())})
		return
	}
	c.JSON(http.StatusOK, struct {
		UUID    string    `json:"uuid"`
		AskedAt time.Time `json:"asked_at"`
	}{UUID: req.UUID, AskedAt: req.AskedAt})
}

// GetQuestion returns one single question queried by the given UUID
func (q *QuestionsHandler) GetQuestion(c *gin.Context) {
	uuid := c.GetString("uuid")
	if c.GetBool("is_admin") {
		uuid = c.Param("uuid")
	}
	question, err := q.QuestionManager.GetQuestionByUUID(c, uuid, c.GetBool("is_admin"))
	if err != nil {
		switch err.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "投稿不存在或已销毁"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("查询投稿失败，错误信息： %s，请联系网站管理员", err.Error())})
		}
		return
	}
	if !c.GetBool("is_admin") && question.AnsweredAt != time.Unix(0, 0) {
		q.VisitChan <- &model.VisitStatus{
			UUID:       uuid,
			VisitedAt:  time.Now(),
			VisitCount: 1,
		}
	}
	c.JSON(http.StatusOK, question)
}

// ListQuestions returns a list of questions queried by given params
func (q *QuestionsHandler) ListQuestions(c *gin.Context) {
	type orderParams struct {
		By       string `json:"by"`
		Reversed bool   `json:"reversed"`
	}
	type listRequest struct {
		Owner       string      `json:"owner"`
		Type        string      `json:"type"`
		OrderParams orderParams `json:"order_params"`
		Days        int32       `json:"day_limit"`
		ReplyStatus int32       `json:"reply_status"`
		PageSize    int32       `json:"page_size"`
		Page        int32       `json:"page"`
	}
	body, err := ioutil.ReadAll(c.Request.Body)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法读取投稿请求，错误信息：%s", err.Error())})
		return
	}
	req := &listRequest{}
	err = json.Unmarshal(body, req)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法解析投稿请求，错误信息：%s", err.Error())})
		return
	}
	_, ok := q.ProfileManager.GetRuneLimitByOwnerNameAndQuestionType(req.Owner, req.Type)
	if !ok {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("未知提问箱主人 %s 或投稿类型 %s", req.Owner, req.Type)})
	}
	questions, totalCount, statusErr := q.QuestionManager.ListQuestions(c, req.Owner, req.Type, req.OrderParams.By, req.OrderParams.Reversed, time.Now().AddDate(0, 0, int(-req.Days)).Unix(), req.PageSize, req.Page, req.ReplyStatus)
	if statusErr != nil {
		switch statusErr.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "没有更多投稿可以列出"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("查询投稿失败，错误信息： %s，请联系网站管理员", statusErr.Error())})
		}
		return
	}
	type resp struct {
		Questions  []*model.Question `json:"questions"`
		TotalCount int32             `json:"total"`
		PageSize   int32             `json:"page_size"`
		Page       int32             `json:"page"`
	}
	c.JSON(http.StatusOK, resp{Questions: questions, TotalCount: totalCount, PageSize: req.PageSize, Page: req.Page})
}

// AnswerQuestion records the answer for one single question queried by the given UUID
func (q *QuestionsHandler) AnswerQuestion(c *gin.Context) {
	type answerReq struct {
		UUID       string `json:"uuid"`
		Answer     string `json:"answer"`
		AnsweredBy string `json:"answered_by"`
	}
	body, err := ioutil.ReadAll(c.Request.Body)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法读取投稿请求，错误信息：%s", err.Error())})
		return
	}
	req := &answerReq{}
	err = json.Unmarshal(body, req)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法解析投稿请求，错误信息：%s", err.Error())})
		return
	}
	question, statusErr := q.QuestionManager.GetQuestionByUUID(c, req.UUID, false)
	if statusErr != nil {
		switch statusErr.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "投稿不存在或已过期销毁"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("查询投稿失败，错误信息： %s，请联系网站管理员", statusErr.Error())})
		}
		return
	}

	question.AnswerText = req.Answer
	question.AnsweredBy = req.AnsweredBy
	question.AnsweredAt = time.Now()

	statusErr = q.QuestionManager.UpdateAnswer(c, question)
	if statusErr != nil {
		switch statusErr.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "投稿不存在或已过期销毁"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("提交回答失败，错误信息： %s，请联系网站管理员", statusErr.Error())})
		}
		return
	}
	c.Status(http.StatusOK)
}

// DeleteQuestion deletes one single question queried by the given UUID
func (q *QuestionsHandler) DeleteQuestion(c *gin.Context) {
	uuid := c.Param("uuid")
	statusErr := q.QuestionManager.MarkAsDeleted(c, uuid)
	if statusErr != nil {
		switch statusErr.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "投稿不存在或已过期销毁"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("查询投稿失败，错误信息： %s，请联系网站管理员", statusErr.Error())})
		}
		return
	}
	c.Status(http.StatusOK)
}
