package handler

import (
	"fmt"
	"io/ioutil"
	"net/http"

	"github.com/anonymous-question-box/internal/domain/repository"
	"github.com/gin-gonic/gin"
)

type FilepondHandler struct {
	TempFileRepo    repository.TempFileRepo
	QuestionManager repository.QuestionManager
}

func (f *FilepondHandler) GenerateFileID(c *gin.Context) {
	c.String(http.StatusOK, "%s", f.TempFileRepo.GenerateTempFileID())
}

func (f *FilepondHandler) Delete(c *gin.Context) {
	buf, _ := ioutil.ReadAll(c.Request.Body)
	f.TempFileRepo.RemoveTempFileByID(string(buf))
	c.Status(http.StatusOK)
}

func (f *FilepondHandler) Process(c *gin.Context) {
	id := f.TempFileRepo.GenerateTempFileID()
	form, _ := c.MultipartForm()
	for _, fileReaders := range form.File {
		for _, fileReader := range fileReaders {
			file, err := fileReader.Open()
			if err != nil {
				c.AbortWithStatusJSON(http.StatusBadRequest, ErrorResp{Error: fmt.Sprintf("无法读取上传的图片，错误信息：%s", err.Error())})
				return
			}
			err = f.TempFileRepo.StoreTempFile(id, fileReader.Filename, file)
			if err != nil {
				c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorResp{Error: fmt.Sprintf("无法暂存上传的图片，错误信息：%s", err.Error())})
				return
			}
		}
	}
	c.String(http.StatusOK, "%s", id)
}
