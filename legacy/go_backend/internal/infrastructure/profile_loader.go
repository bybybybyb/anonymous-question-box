package infrastructure

import (
	"log"
	"time"

	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/spf13/viper"
)

var WebsiteProfile *model.WebsiteProfile

func LoadProfiles() error {
	WebsiteProfile = &model.WebsiteProfile{}
	Profiles := make(map[string]*model.OwnerProfile)
	profiles := []*model.OwnerProfile{}
	err := viper.UnmarshalKey("owner_profiles", &profiles)
	if err != nil {
		return err
	}
	for _, profile := range profiles {
		for _, qt := range profile.QuestionTypes {
			if qt.StartTimeStr != "" {
				startTime, err := time.Parse(time.RFC3339, qt.StartTimeStr)
				if err != nil {
					log.Printf("failed to parse start time from config for owner %s qType %s, %s\n", profile.Name, qt.Name, err.Error())
					continue
				}
				qt.StartTime = startTime
			}
			if qt.EndTimeStr != "" {
				endTime, err := time.Parse(time.RFC3339, qt.EndTimeStr)
				if err != nil {
					log.Printf("failed to parse end time from config for owner %s qType %s, %s\n", profile.Name, qt.Name, err.Error())
					continue
				}
				qt.EndTime = endTime
			}
		}
		Profiles[profile.Name] = profile
	}
	WebsiteProfile.OwnerProfiles = Profiles

	WebsiteMetadata := &model.WebsiteMetadata{Introductions: []string{}, ConsolePrints: []string{}}
	metadata := viper.GetStringMapStringSlice("website_metadata")
	if intros, ok := metadata["introductions"]; ok {
		WebsiteMetadata.Introductions = append(WebsiteMetadata.Introductions, intros...)
	}
	if prints, ok := metadata["console_prints"]; ok {
		WebsiteMetadata.ConsolePrints = append(WebsiteMetadata.ConsolePrints, prints...)
	}
	adminInfo := viper.GetStringMapString("website_metadata.admin")
	if adminInfo != nil {
		WebsiteMetadata.AdminInfo = adminInfo
	}
	WebsiteProfile.Metadata = WebsiteMetadata
	return nil
}
