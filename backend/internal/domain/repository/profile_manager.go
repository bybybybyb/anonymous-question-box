package repository

import (
	"github.com/anonymous-question-box/internal/infrastructure"
	"github.com/spf13/viper"
)

type LocalProfileManager struct{}

func (p *LocalProfileManager) GetRuneLimitByOwnerNameAndQuestionType(ownerName string, qTypeName string) (int, bool) {
	profile, ok := infrastructure.Profiles[ownerName]
	if !ok {
		return 0, false
	}
	questionType, ok := profile.QuestionTypes[qTypeName]
	if !ok {
		return 0, false
	}
	if questionType.RuneLimit == 0 {
		return viper.GetInt("default_rune_limit"), true
	}
	return questionType.RuneLimit, true
}
