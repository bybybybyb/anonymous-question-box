package model

import (
	"time"
)

type Question struct {
	ID         int32     `json:"-"`
	UUID       string    `json:"-"`
	Type       string    `json:"type,omitempty"`
	Owner      string    `json:"owner"`
	Text       string    `json:"text"`
	AskedAt    time.Time `json:"asked_at"`
	AnswerText string    `json:"answer,omitempty"`
	AnsweredAt time.Time `json:"answered_at,omitempty"`
}
