package model

import (
	"time"
)

type Question struct {
	ID         int32     `json:"-"`
	UUID       string    `json:"uuid"`
	Type       string    `json:"type"`
	Owner      string    `json:"owner"`
	Text       string    `json:"text"`
	WordCount  int32     `json:"word_count"`
	AskedAt    time.Time `json:"asked_at"`
	AnswerText string    `json:"answer"`
	AnsweredAt time.Time `json:"answered_at"`
}
