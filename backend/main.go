package main

import (
	"flag"
	"fmt"
	"github.com/anonymous-question-box/internal/infrastructure"
	"github.com/anonymous-question-box/internal/server"
	"github.com/fsnotify/fsnotify"
	"github.com/fvbock/endless"
	"github.com/gin-contrib/pprof"
	"github.com/spf13/viper"
	"log"
	"sync"
	"syscall"
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
	r, exit := server.SetupRoutes()
	wg := &sync.WaitGroup{}
	gracefulStopVisitMonitor := func() {
		exit <- wg
		wg.Wait()
	}
	// profiling
	pprof.Register(r)
	// start server
	srv := endless.NewServer(fmt.Sprintf("%s:%s", viper.GetString("host"), viper.GetString("port")), r)
	srv.RegisterSignalHook(endless.PRE_SIGNAL, syscall.SIGTERM, gracefulStopVisitMonitor)
	srv.RegisterSignalHook(endless.PRE_SIGNAL, syscall.SIGKILL, gracefulStopVisitMonitor)
	srv.RegisterSignalHook(endless.PRE_SIGNAL, syscall.SIGINT, gracefulStopVisitMonitor)
	err = srv.ListenAndServe()
	if err != nil {
		log.Printf("%+v", err.Error())
	}
}
