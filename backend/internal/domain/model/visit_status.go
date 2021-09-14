package model

import "time"

type VisitStatus struct {
	UUID       string
	VisitedAt  time.Time
	VisitCount int32
}
