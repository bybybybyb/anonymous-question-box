package handler

import (
	"encoding/json"
	"fmt"
	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/anonymous-question-box/internal/domain/repository"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/spf13/viper"
	"io/ioutil"
	"net/http"
	"time"
	"unicode/utf8"
)

type QuestionsHandler struct {
	ProfileManager  repository.ProfileManager
	TokenManager    repository.TokenManager
	QuestionManager repository.QuestionManager
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
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法读取问题请求，错误信息：%s", err.Error())})
		return
	}
	req := &model.Question{
		UUID:    c.GetString("uuid"),
		AskedAt: time.Now(),
	}
	err = json.Unmarshal(body, req)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法解析问题请求，错误信息：%s", err.Error())})
		return
	}
	runeLimit, ok := q.ProfileManager.GetRuneLimitByOwnerNameAndQuestionType(req.Owner, req.Type)
	if !ok {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("未知提问箱主人 %s 或问题类型 %s", req.Owner, req.Type)})
		return
	}
	if utf8.RuneCountInString(req.Text) > runeLimit {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("问题长度超过最大限度 %d", runeLimit)})
		return
	}
	err = q.QuestionManager.InsertQuestion(c, req)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("提交失败，错误信息：%s，请联系网站管理员", err.Error())})
		return
	}
	c.Status(http.StatusOK)
}

// GetQuestion returns one single question queried by the given UUID
func (q *QuestionsHandler) GetQuestion(c *gin.Context) {
	question, err := q.QuestionManager.GetQuestionByUUID(c, c.GetString("uuid"), time.Now().AddDate(0, 0, -viper.GetInt("question_expiration_days")).Unix())
	if err != nil {
		switch err.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "问题不存在或已过期销毁"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("查询问题失败，错误信息： %s，请联系网站管理员", err.Error())})
		}
		return
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
		Days        int         `json:"day_limit"`
		ReplyStatus int         `json:"reply_status"`
		RowsPerPage int         `json:"rows_per_page"`
		Page        int         `json:"page"`
	}
	body, err := ioutil.ReadAll(c.Request.Body)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法读取问题请求，错误信息：%s", err.Error())})
		return
	}
	req := &listRequest{}
	err = json.Unmarshal(body, req)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法解析问题请求，错误信息：%s", err.Error())})
		return
	}
	_, ok := q.ProfileManager.GetRuneLimitByOwnerNameAndQuestionType(req.Owner, req.Type)
	if !ok {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("未知提问箱主人 %s 或问题类型 %s", req.Owner, req.Type)})
	}
	questions, statusErr := q.QuestionManager.ListQuestions(c, req.Owner, req.Type, req.OrderParams.By, req.OrderParams.Reversed, time.Now().AddDate(0, 0, -req.Days).Unix(), req.RowsPerPage, req.Page, req.ReplyStatus)
	if statusErr != nil {
		switch statusErr.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "没有更多问题可以列出"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("查询问题失败，错误信息： %s，请联系网站管理员", statusErr.Error())})
		}
		return
	}
	c.JSON(http.StatusOK, questions)
}

// AnswerQuestion records the answer for one single question queried by the given UUID
func (q *QuestionsHandler) AnswerQuestion(c *gin.Context) {
	type answerReq struct {
		UUID   string `json:"uuid"`
		Answer string `json:"answer"`
	}
	body, err := ioutil.ReadAll(c.Request.Body)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法读取问题请求，错误信息：%s", err.Error())})
		return
	}
	req := &answerReq{}
	err = json.Unmarshal(body, req)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法解析问题请求，错误信息：%s", err.Error())})
		return
	}
	question, statusErr := q.QuestionManager.GetQuestionByUUID(c, req.UUID, time.Now().AddDate(0, 0, -viper.GetInt("question_expiration_days")).Unix())
	if statusErr != nil {
		switch statusErr.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "问题不存在或已过期销毁"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("查询问题失败，错误信息： %s，请联系网站管理员", statusErr.Error())})
		}
		return
	}

	question.AnswerText = req.Answer
	question.AnsweredAt = time.Now()

	statusErr = q.QuestionManager.UpdateAnswer(c, question)
	if statusErr != nil {
		switch statusErr.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "问题不存在或已过期销毁"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("提交回答失败，错误信息： %s，请联系网站管理员", statusErr.Error())})
		}
		return
	}
	c.Status(http.StatusOK)
}

// DeleteQuestion deletes one single question queried by the given UUID
func (q *QuestionsHandler) DeleteQuestion(c *gin.Context) {
	uuid := c.Query("uuid")
	statusErr := q.QuestionManager.MarkAsDeleted(c, uuid)
	if statusErr != nil {
		switch statusErr.Code() {
		case http.StatusNotFound:
			c.AbortWithStatusJSON(http.StatusNotFound, ErrorResp{Error: "问题不存在或已过期销毁"})
		case http.StatusInternalServerError:
			c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("查询问题失败，错误信息： %s，请联系网站管理员", statusErr.Error())})
		}
		return
	}
	c.Status(http.StatusOK)
}
