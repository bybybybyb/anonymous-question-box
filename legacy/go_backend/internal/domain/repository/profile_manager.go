package repository

import (
	"time"

	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/anonymous-question-box/internal/infrastructure"
	"github.com/spf13/viper"
)

type LocalProfileManager struct{}

func (p *LocalProfileManager) GetRuneLimitByOwnerNameAndQuestionType(ownerName, qTypeName string) (int32, bool) {
	questionType := getQuestionType(ownerName, qTypeName)
	if questionType != nil {
		if questionType.RuneLimit == 0 {
			return viper.GetInt32("default_rune_limit"), true
		}
		return questionType.RuneLimit, true
	}
	return viper.GetInt32("default_rune_limit"), false
}

func (p *LocalProfileManager) GetFlightTimeByOwnerNameAndQuestionType(ownerName, qTypeName string) (time.Time, time.Time, bool) {
	questionType := getQuestionType(ownerName, qTypeName)
	if questionType != nil && questionType.StartTimeStr != "" && questionType.EndTimeStr != "" {
		return questionType.StartTime, questionType.EndTime, true
	}
	return time.Time{}, time.Time{}, false
}

func (p *LocalProfileManager) IsImageSupportedByOwnerNameAndQuestionType(ownerName, qTypeName string) bool {
	questionType := getQuestionType(ownerName, qTypeName)
	return questionType != nil && questionType.SupportImage
}

func getQuestionType(ownerName, qTypeName string) *model.QuestionType {
	profile, ok := infrastructure.WebsiteProfile.OwnerProfiles[ownerName]
	if !ok {
		return nil
	}
	questionType, ok := profile.QuestionTypes[qTypeName]
	if !ok {
		return nil
	}
	return questionType
}
