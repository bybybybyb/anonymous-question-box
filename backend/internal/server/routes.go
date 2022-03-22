package server

import (
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/anonymous-question-box/internal/domain/repository"
	"github.com/anonymous-question-box/internal/infrastructure"
	"github.com/anonymous-question-box/internal/server/handler"
	"github.com/anonymous-question-box/internal/usecase"
	"github.com/gin-gonic/gin"
	"github.com/spf13/viper"
)

func SetupRoutes() (*gin.Engine, chan bool, *sync.WaitGroup) {
	visitChan := make(chan *model.VisitStatus)
	exit := make(chan bool)
	wg := &sync.WaitGroup{}

	ossID := os.Getenv("OSS_ID")
	if ossID == "" {
		ossID = viper.GetString("oss_id")
	}
	ossKey := os.Getenv("OSS_KEY")
	if ossKey == "" {
		ossKey = viper.GetString("oss_key")
	}
	ossCDNKey := os.Getenv("OSS_CDN_KEY")
	if ossCDNKey == "" {
		ossCDNKey = viper.GetString("oss_cdn_key")
	}
	qManager := &repository.SQLiteQuestionManager{}
	tempFileRepo := &repository.LocalTempFileRepo{RootDir: viper.GetString("temp_file_root_dir"), IDToLocalPath: make(map[string]string), Mutex: &sync.Mutex{}}
	persistFileRepo, err := repository.NewTencentOSSPersistFileRepo(viper.GetString("oss_url"), viper.GetString("oss_cdn_url"), ossID, ossKey, ossCDNKey, viper.GetString("oss_bucket"))
	if err != nil {
		panic(err)
	}

	authHandler := &handler.AuthHandler{TokenManager: &repository.JWTManager{}}
	questionsHandler := &handler.QuestionsHandler{
		ProfileManager:  &repository.LocalProfileManager{},
		TokenManager:    &repository.JWTManager{},
		QuestionManager: qManager,
		TempFileRepo:    tempFileRepo,
		PersistFileRepo: persistFileRepo,
		VisitChan:       visitChan}
	fileHandler := &handler.FilepondHandler{TempFileRepo: tempFileRepo, QuestionManager: qManager}

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
	return setupRoutes(authHandler, questionsHandler, fileHandler), exit, wg
}

func setupRoutes(authHandler *handler.AuthHandler, questionsHandler *handler.QuestionsHandler, fileHandler *handler.FilepondHandler) *gin.Engine {
	r := gin.Default()
	// some basic one liner handlers
	r.GET("/checkalive", func(c *gin.Context) {
		c.String(http.StatusOK, "pong")
	})
	r.GET("/profiles", func(c *gin.Context) {
		c.JSON(http.StatusOK, infrastructure.WebsiteProfile)
	})
	r.GET("/new", questionsHandler.NewQuestionToken)

	r.POST("/image/process", fileHandler.Process)
	r.DELETE("/image/process", fileHandler.Delete)

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
