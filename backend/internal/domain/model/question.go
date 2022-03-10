package model

import (
	"time"
)

type Question struct {
	ID            int32     `json:"-"`
	UUID          string    `json:"uuid"`
	Type          string    `json:"type"`
	Owner         string    `json:"owner"`
	Text          string    `json:"text"`
	WordCount     int32     `json:"word_count"`
	AskedAt       time.Time `json:"asked_at"`
	AnswerText    string    `json:"answer"`
	AnsweredAt    time.Time `json:"answered_at"`
	AnsweredBy    string    `json:"answered_by"`
	LastVisitedAt time.Time `json:"last_visited_at"`
	VisitCount    int32     `json:"visit_count"`
	ImageIDs      []string  `json:"image_ids"`
	Images        []Image   `json:"images"`
}

type Image struct {
	Filename string `json:"filename"`
	URL      string `json:"url"`
}

type ImageMetadata struct {
	QuestionUUID string
	Key          string
}
