package repository

import (
	"context"
	"fmt"
	"time"

	"github.com/golang-jwt/jwt"
	"github.com/spf13/viper"
)

type JWTManager struct {
}

type customClaims struct {
	UUID    string `json:"uuid"`
	IsAdmin bool   `json:"is_admin"`
	jwt.StandardClaims
}

func (j *JWTManager) GenerateToken(ctx context.Context, uuid string, isAdmin bool) (string, error) {
	claims := &customClaims{
		uuid,
		isAdmin,
		jwt.StandardClaims{
			// +10 to make sure the token does not expire before the question expiring
			ExpiresAt: time.Now().Add(time.Hour * 24 * time.Duration(viper.GetInt("question_expiration_time")+10)).Unix(),
			IssuedAt:  time.Now().Unix(),
		},
	}
	// never expose backend endpoints to public since here we use a weak signing method
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	t, err := token.SignedString([]byte(viper.GetString("jwt_secret_key")))
	if err != nil {
		return "", err
	}
	return t, nil
}

func (j *JWTManager) ValidateToken(ctx context.Context, encodedToken string) (string, bool, error) {
	token, err := jwt.Parse(encodedToken, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("invalid token signing method %s", token.Header["alg"])
		}
		return []byte(viper.GetString("jwt_secret_key")), nil
	})
	if err != nil {
		return "", false, err
	}
	if claims, ok := token.Claims.(jwt.MapClaims); ok && token.Valid {
		return claims["uuid"].(string), claims["is_admin"].(bool), nil
	}
	return "", false, fmt.Errorf("validation failed or decoding failed")
}
