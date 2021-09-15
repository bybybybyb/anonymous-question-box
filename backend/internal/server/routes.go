package server

import (
	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/anonymous-question-box/internal/domain/repository"
	"github.com/anonymous-question-box/internal/infrastructure"
	"github.com/anonymous-question-box/internal/server/handler"
	"github.com/anonymous-question-box/internal/usecase"
	"github.com/gin-gonic/gin"
	"net/http"
	"sync"
	"time"
)

func SetupRoutes() (*gin.Engine, chan bool, *sync.WaitGroup) {
	qManager := &repository.SQLiteQuestionManager{}
	visitChan := make(chan *model.VisitStatus)
	exit := make(chan bool)
	authHandler := &handler.AuthHandler{TokenManager: &repository.JWTManager{}}
	questionsHandler := &handler.QuestionsHandler{ProfileManager: &repository.LocalProfileManager{}, TokenManager: &repository.JWTManager{}, QuestionManager: qManager, VisitChan: visitChan}
	wg := &sync.WaitGroup{}
	visitMonitor := usecase.VisitMonitor{
		QuestionManager:     qManager,
		VisitChan:           visitChan,
		Exit:                exit,
		PerQuestionVisitMap: make(map[string]*model.VisitStatus),
		Interval:            usecase.DefaultUpdateInterval * time.Second,
		Ticker:              time.NewTicker(usecase.DefaultUpdateInterval * time.Second),
		Wg:                  wg,
	}
	go visitMonitor.Run()
	return setupRoutes(authHandler, questionsHandler), exit, wg
}

func setupRoutes(authHandler *handler.AuthHandler, questionsHandler *handler.QuestionsHandler) *gin.Engine {
	r := gin.Default()
	// some basic one liner handlers
	r.GET("/checkalive", func(c *gin.Context) {
		c.String(http.StatusOK, "pong")
	})
	r.GET("/profiles", func(c *gin.Context) {
		c.JSON(http.StatusOK, infrastructure.WebsiteProfile)
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
