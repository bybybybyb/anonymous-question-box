package infrastructure

import (
	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/spf13/viper"
)

var Profiles map[string]model.Profile
var WebsiteMetadataStore model.WebsiteMetadata

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

	WebsiteMetadataStore = model.WebsiteMetadata{Introductions: []string{}, ConsolePrints: []string{}}
	metadata := viper.GetStringMapStringSlice("website_metadata")
	if intros, ok := metadata["introductions"]; ok {
		WebsiteMetadataStore.Introductions = append(WebsiteMetadataStore.Introductions, intros...)
	}
	if prints, ok := metadata["console_prints"]; ok {
		WebsiteMetadataStore.ConsolePrints = append(WebsiteMetadataStore.ConsolePrints, prints...)
	}
	return nil
}
