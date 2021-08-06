package model

type Profile struct {
	Name          string                  `mapstructure:"name" json:"name"`
	ColorTheme    ColorTheme              `mapstructure:"color_theme" json:"color_theme"`
	QuestionTypes map[string]QuestionType `mapstructure:"question_types" json:"question_types"`
}

type ColorTheme struct {
	PrimaryColor   string `mapstructure:"primary_color" json:"primary_color"`
	SecondaryColor string `mapstructure:"secondary_color" json:"secondary_color"`
}

type QuestionType struct {
	Name            string `mapstructure:"name" json:"name"`
	Description     string `mapstructure:"description" json:"description"`
	RuneLimit       int32  `mapstructure:"rune_limit" json:"rune_limit"`
	BackgroundClass string `mapstructure:"background_class" json:"background_class"`
}

type WebsiteMetadata struct {
	Introductions []string `json:"introductions"`
	ConsolePrints []string `json:"console_prints"`
}
