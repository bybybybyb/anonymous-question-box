package infrastructure

import (
	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/spf13/viper"
)

var Profiles map[string]model.Profile

func LoadProfiles() error {
	Profiles = make(map[string]model.Profile)
	profiles := []model.Profile{}
	err := viper.UnmarshalKey("owner_profiles", &profiles)
	if err != nil {
		return err
	}
	for _, profile := range profiles {
		Profiles[profile.Name] = profile
	}
	return nil
}
