package handler

import "github.com/spf13/viper"

type ErrorResp struct {
	Error string `json:"error"`
}

func getRuneLimitFromConfig(qOwner, qType string) (int, bool) {
	tmp, ok := viper.Get("owners").(map[string]interface{})
	if ok && tmp != nil {
		tmp, ok := tmp[qOwner].(map[string]interface{})
		if ok && tmp != nil {
			tmp, ok := tmp[qType].(map[string]interface{})
			if ok && tmp != nil {
				return tmp["rune_limit"].(int), true
			}
		}
	}
	return viper.GetInt("default_rune_limit"), false
}
