package model

import (
	"time"
)

type Question struct {
	ID         int32     `json:"-"`
	UUID       string    `json:"-"`
	Type       string    `json:"question_type,omitempty"`
	Owner      string    `json:"question_owner"`
	Text       string    `json:"question"`
	AskedAt    time.Time `json:"asked_at"`
	AnswerText string    `json:"answer,omitempty"`
	AnsweredAt time.Time `json:"answered_at,omitempty"`
	Deleted    bool      `json:"-"`
}
