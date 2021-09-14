package usecase

import (
	"context"
	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/anonymous-question-box/internal/domain/repository"
	"log"
	"sync"
	"time"
)

const DefaultUpdateInterval = 10

type VisitMonitor struct {
	QuestionManager     repository.QuestionManager
	VisitChan           chan *model.VisitStatus
	Exit                chan *sync.WaitGroup
	PerQuestionVisitMap map[string]*model.VisitStatus
	Interval            time.Duration
	Ticker              *time.Ticker
}

func (v *VisitMonitor) Run() {
	for {
		select {
		case visit := <-v.VisitChan:
			if prevVisit, ok := v.PerQuestionVisitMap[visit.UUID]; ok {
				visit.VisitCount += prevVisit.VisitCount
			}
			v.PerQuestionVisitMap[visit.UUID] = visit
		case <-v.Ticker.C:
			v.onTicker()
		case wg := <-v.Exit:
			wg.Add(1)
			log.Printf("stopping visit monitor...\n")
			v.onTicker()
			wg.Done()
			log.Printf("visit monitor stopped.\n")
			return
		}
	}
}

func (v *VisitMonitor) onTicker() {
	if len(v.PerQuestionVisitMap) > 0 {
		ctx, cancel := context.WithTimeout(context.Background(), time.Duration(v.Interval/2))
		defer cancel()
		err := v.QuestionManager.RecordVisit(ctx, v.PerQuestionVisitMap)
		if err != nil {
			log.Printf("failed to update visit records, err: %s\n", err.Error())
		} else {
			v.PerQuestionVisitMap = make(map[string]*model.VisitStatus)
		}
	}
}
