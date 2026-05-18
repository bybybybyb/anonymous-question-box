package main

import (
	"context"
	"flag"
	"fmt"
	"github.com/anonymous-question-box/internal/infrastructure"
	"github.com/anonymous-question-box/internal/server"
	"github.com/fsnotify/fsnotify"
	"github.com/gin-contrib/pprof"
	"github.com/spf13/viper"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	configFlag := flag.String("c", "./config/config.yaml", "path to the config yaml")
	flag.Parse()

	// server config
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.SetConfigFile(*configFlag)
	viper.ReadInConfig()
	viper.WatchConfig()
	viper.OnConfigChange(func(e fsnotify.Event) {
		log.Printf("detected config file change\n")
		err := infrastructure.LoadProfiles()
		if err != nil {
			log.Printf("failed to reload the config file: %s", err.Error())
		}
	})

	// default configs
	viper.SetDefault("host", "")
	viper.SetDefault("port", "8080")
	// 默认字数限制
	viper.SetDefault("default_rune_limit", 500)

	// inits
	err := infrastructure.InitSQLiteDB()
	if err != nil {
		panic(err.Error())
	}
	err = infrastructure.LoadProfiles()
	if err != nil {
		panic(err.Error())
	}
	r, exit, wg := server.SetupRoutes()
	// profiling
	pprof.Register(r)
	// start server
	signalChan := make(chan os.Signal, 1)
	signal.Notify(signalChan, syscall.SIGINT, syscall.SIGTERM)

	srv := &http.Server{
		Addr:    fmt.Sprintf("%s:%s", viper.GetString("host"), viper.GetString("port")),
		Handler: r,
	}
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %s\n", err)
		}
	}()

	<-signalChan
	log.Println("shutting down gracefully, press Ctrl+C again to force")

	exit <- true
	wg.Wait()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("server forced to shutdown: ", err)
	}

	log.Println("server exiting")
}
