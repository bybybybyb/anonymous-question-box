package server

import (
	"github.com/anonymous-question-box/internal/domain/repository"
	"github.com/anonymous-question-box/internal/infrastructure"
	"github.com/anonymous-question-box/internal/server/handler"
	"github.com/gin-gonic/gin"
	"net/http"
)

func SetupRoutes() *gin.Engine {
	r := gin.Default()
	authHandler := &handler.AuthHandler{TokenManager: &repository.JWTManager{}}
	questionsHandler := &handler.QuestionsHandler{ProfileManager: &repository.LocalProfileManager{}, TokenManager: &repository.JWTManager{}, QuestionManager: &repository.SQLiteQuestionManager{}}

	// some basic one liner handlers
	r.GET("/checkalive", func(c *gin.Context) {
		c.String(http.StatusOK, "pong")
	})
	r.GET("/profiles", func(c *gin.Context) {
		c.JSON(http.StatusOK, infrastructure.Profiles)
	})

	r.GET("/new", questionsHandler.NewQuestionToken)

	userAuthorized := r.Group("/questions", authHandler.Authenticate, authHandler.BlockOwner)
	userAuthorized.GET("/question", questionsHandler.GetQuestion)
	userAuthorized.POST("/submit", questionsHandler.SubmitNewQuestion)

	ownerAuthorized := r.Group("/owner", authHandler.Authenticate, authHandler.AuthorizeOwner)
	ownerAuthorized.GET("", authHandler.GetOwnerInfo)
	ownerAuthorized.POST("/questions", questionsHandler.ListQuestions)
	ownerAuthorized.GET("/questions/:uuid", questionsHandler.GetQuestion)
	ownerAuthorized.PUT("/questions/:uuid/answer", questionsHandler.AnswerQuestion)
	ownerAuthorized.DELETE("/questions/:uuid/delete", questionsHandler.DeleteQuestion)

	return r
}
