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
	UUID string `json:"uuid"`
	jwt.StandardClaims
}

// GenerateToken generates a JWT token encoding the UUID given into it
func (j *JWTManager) GenerateToken(ctx context.Context, uuid string) (string, error) {
	claims := &customClaims{
		uuid,
		jwt.StandardClaims{
			// +10 to make sure the token does not expire before the question expiring
			ExpiresAt: time.Now().Add(time.Hour * 24 * time.Duration(viper.GetInt("question_expiration_time")+10)).Unix(),
			IssuedAt:  time.Now().Unix(),
		},
	}
	// the token is purely for passing values so it is fine to use a weak siging method here
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	t, err := token.SignedString([]byte(viper.GetString("jwt_secret_key")))
	if err != nil {
		return "", err
	}
	return t, nil
}

// ValidateToken validates a JWT token and extract UUID from it. It also does some magic to grant admin permissions
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
		// a small trick here to grant special permissions
		v, ok := claims[viper.GetString("magic_spell")]
		if ok {
			return v.(string), true, nil
		}
		uuid, ok := claims["uuid"]
		if ok {
			return uuid.(string), false, nil
		}
	}
	return "", false, fmt.Errorf("validation failed or decoding failed")
}
