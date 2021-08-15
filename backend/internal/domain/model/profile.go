package model

import "time"

type Profile struct {
	Name          string                   `mapstructure:"name" json:"name"`
	Colors        Colors                   `mapstructure:"colors" json:"colors"`
	QuestionTypes map[string]*QuestionType `mapstructure:"question_types" json:"question_types"`
}

type Colors struct {
	PrimaryColor   string `mapstructure:"primary_color" json:"primary_color"`
	SecondaryColor string `mapstructure:"secondary_color" json:"secondary_color"`
}

type QuestionType struct {
	Name         string `mapstructure:"name" json:"name"`
	Description  string `mapstructure:"description" json:"description"`
	RuneLimit    int32  `mapstructure:"rune_limit" json:"rune_limit"`
	StartTimeStr string `mapstructure:"start_time" json:"start_time"`
	StartTime    time.Time
	EndTimeStr   string `mapstructure:"end_time" json:"end_time"`
	EndTime      time.Time
	Theme        Theme `mapstructure:"theme" json:"theme"`
}

type Theme struct {
	Name            string `mapstructure:"name" json:"name"`
	BackgroundClass string `mapstructure:"background_class" json:"background_class"`
}

type WebsiteMetadata struct {
	Introductions []string `json:"introductions"`
	ConsolePrints []string `json:"console_prints"`
}
