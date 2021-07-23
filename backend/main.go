package main

import (
	"flag"
	"fmt"
	"github.com/anonymous-question-box/internal/infrastructure"
	"github.com/anonymous-question-box/internal/server"
	"github.com/spf13/viper"
)

func main() {
	configFlag := flag.String("config", "../config/config.yaml", "path to the config file")

	// configs
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.SetConfigFile(*configFlag)
	viper.ReadInConfig()
	// default configs
	viper.SetDefault("host", "")
	viper.SetDefault("port", "8080")
	// 默认问题自动过期时间
	viper.SetDefault("question_expiration_days", 60)
	// 默认字数限制
	viper.SetDefault("default_rune_limit", 500)
	// inits
	err := infrastructure.InitSQLiteDB()
	if err != nil {
		panic(err.Error())
	}

	// start server
	r := server.SetupRoutes()
	r.Run(fmt.Sprintf("%s:%s", viper.GetString("host"), viper.GetString("port")))
}
