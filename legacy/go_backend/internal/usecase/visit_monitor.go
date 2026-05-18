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
	Exit                chan bool
	PerQuestionVisitMap map[string]*model.VisitStatus
	Interval            time.Duration
	Ticker              *time.Ticker
	Wg                  *sync.WaitGroup
}

func (v *VisitMonitor) Run() {
	v.Wg.Add(1)
	defer v.Wg.Done()
	for {
		select {
		case visit := <-v.VisitChan:
			if prevVisit, ok := v.PerQuestionVisitMap[visit.UUID]; ok {
				visit.VisitCount += prevVisit.VisitCount
			}
			v.PerQuestionVisitMap[visit.UUID] = visit
		case <-v.Ticker.C:
			ctx, cancel := context.WithTimeout(context.Background(), time.Duration(v.Interval/2))
			defer cancel()
			v.onTicker(ctx)
		case <-v.Exit:
			log.Printf("stopping visit monitor...\n")
			ctx, cancel := context.WithTimeout(context.Background(), time.Duration(v.Interval/2))
			defer cancel()
			v.onTicker(ctx)
			log.Printf("visit monitor stopped.\n")
			return
		}
	}
}

func (v *VisitMonitor) onTicker(ctx context.Context) {
	if len(v.PerQuestionVisitMap) > 0 {
		err := v.QuestionManager.RecordVisit(ctx, v.PerQuestionVisitMap)
		if err != nil {
			log.Printf("failed to update visit records, err: %s\n", err.Error())
		} else {
			v.PerQuestionVisitMap = make(map[string]*model.VisitStatus)
		}
	}
}
