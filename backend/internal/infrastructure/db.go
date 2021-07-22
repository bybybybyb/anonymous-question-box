package infrastructure

import (
	"database/sql"
	_ "github.com/mattn/go-sqlite3"
	"github.com/spf13/viper"
)

var DBConn *sql.DB

func InitSQLiteDB() error {
	db, err := sql.Open("sqlite3", viper.GetString("db_path"))
	if err != nil {
		return err
	}
	db.SetMaxOpenConns(viper.GetInt("db_max_connections"))
	DBConn = db
	return db.Ping()
}
