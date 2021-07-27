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
	GetQuestionByUUID(ctx context.Context, uuid string, due int64) (*model.Question, StatusError)
	ListQuestions(ctx context.Context, qOwner, qType, orderBy string, orderReversed bool, due int64, rowsPerPage, page, replyStatus int32) ([]*model.Question, int32, StatusError)
	InsertQuestion(ctx context.Context, question *model.Question) StatusError
	UpdateAnswer(ctx context.Context, question *model.Question) StatusError
	MarkAsDeleted(ctx context.Context, uuid string) StatusError
}

type ProfileManager interface {
	GetRuneLimitByOwnerNameAndQuestionType(ownerName string, qTypeName string) (int32, bool)
}
