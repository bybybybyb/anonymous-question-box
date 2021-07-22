package repository

import (
	"context"
	"github.com/anonymous-question-box/internal/domain/model"
)

type TokenManager interface {
	GenerateToken(ctx context.Context, uuid string) (string, error)
	ValidateToken(ctx context.Context, token string) (string, bool, error)
}

type QuestionManager interface {
	GetQuestionByUUID(ctx context.Context, uuid string) (*model.Question, error)
	ListQuestions(ctx context.Context, qOwner, qType, orderBy string, rowsPerPage, page int) ([]*model.Question, error)
	InsertQuestion(ctx context.Context, question *model.Question) error
	UpdateAnswer(ctx context.Context, question *model.Question) error
	MarkAsDeleted(ctx context.Context, question *model.Question) error
}
