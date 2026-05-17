package model

import "time"

type WebsiteProfile struct {
	OwnerProfiles map[string]*OwnerProfile `json:"owner_profiles"`
	Metadata      *WebsiteMetadata         `json:"metadata"`
}
type OwnerProfile struct {
	Name          string                   `mapstructure:"name" json:"name"`
	Colors        Colors                   `mapstructure:"colors" json:"colors"`
	QuestionTypes map[string]*QuestionType `mapstructure:"question_types" json:"question_types"`
}

type Colors struct {
	PrimaryColor   string `mapstructure:"primary_color" json:"primary_color"`
	SecondaryColor string `mapstructure:"secondary_color" json:"secondary_color"`
}

type QuestionType struct {
	Name         string    `mapstructure:"name" json:"name"`
	Description  string    `mapstructure:"description" json:"description"`
	RuneLimit    int32     `mapstructure:"rune_limit" json:"rune_limit"`
	StartTimeStr string    `mapstructure:"start_time" json:"start_time,omitempty"`
	StartTime    time.Time `json:"-"`
	EndTimeStr   string    `mapstructure:"end_time" json:"end_time,omitempty"`
	EndTime      time.Time `json:"-"`
	Theme        Theme     `mapstructure:"theme" json:"theme"`
	SupportImage bool      `mapstructure:"support_image" json:"support_image"`
}

type Theme struct {
	Name            string `mapstructure:"name" json:"name"`
	BackgroundClass string `mapstructure:"background_class" json:"background_class"`
}

type WebsiteMetadata struct {
	Introductions []string          `json:"introductions"`
	ConsolePrints []string          `json:"console_prints"`
	AdminInfo     map[string]string `mapstructure:"admin" json:"admin"`
}
