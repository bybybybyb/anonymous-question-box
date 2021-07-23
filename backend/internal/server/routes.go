package server

import (
	"github.com/anonymous-question-box/internal/domain/repository"
	"github.com/anonymous-question-box/internal/server/handler"
	"github.com/gin-gonic/gin"
	"net/http"
)

func SetupRoutes() *gin.Engine {
	r := gin.Default()
	authHandler := &handler.AuthHandler{TokenManager: &repository.JWTManager{}}
	questionsHandler := &handler.QuestionsHandler{TokenManager: &repository.JWTManager{}, QuestionManager: &repository.SQLiteQuestionManager{}}

	// checkalive
	r.GET("/checkalive", func(c *gin.Context) {
		c.String(http.StatusOK, "pong")
	})

	r.GET("/new", questionsHandler.NewQuestionToken)

	userAuthorized := r.Group("/questions", authHandler.Authenticate, authHandler.BlockOwner)
	userAuthorized.GET("/question", questionsHandler.GetQuestion)
	userAuthorized.POST("/submit", questionsHandler.SubmitNewQuestion)

	ownerAuthorized := r.Group("/owner", authHandler.Authenticate, authHandler.AuthorizeOwner)
	ownerAuthorized.POST("/questions", questionsHandler.ListQuestions)
	ownerAuthorized.POST("/questions/answer", questionsHandler.AnswerQuestion)
	ownerAuthorized.DELETE("/questions/delete", questionsHandler.DeleteQuestion)

	return r
}
