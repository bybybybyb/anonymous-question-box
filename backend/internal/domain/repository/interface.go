package repository

import (
	"context"
	"io"
	"net/url"
	"time"

	"github.com/anonymous-question-box/internal/domain/model"
)

type TokenManager interface {
	GenerateToken(ctx context.Context, uuid string) (string, error)
	ValidateToken(ctx context.Context, token string) (string, bool, error)
}

type QuestionManager interface {
	GetQuestionByUUID(ctx context.Context, uuid string, withVisitInfo bool) (*model.Question, StatusError)
	ListQuestions(ctx context.Context, qOwner, qType, orderBy string, orderReversed bool, due int64, rowsPerPage, page, replyStatus int32) ([]*model.Question, int32, StatusError)
	InsertQuestion(ctx context.Context, question *model.Question) StatusError
	UpdateAnswer(ctx context.Context, question *model.Question) StatusError
	MarkAsDeleted(ctx context.Context, uuid string) StatusError
	RecordVisit(ctx context.Context, PerQuestionVisitMap map[string]*model.VisitStatus) StatusError
	StoreImageMetadata(ctx context.Context, imageMetadata []*model.ImageMetadata) StatusError
	GetImageMetadataByUUID(ctx context.Context, uuid string) ([]*model.ImageMetadata, StatusError)
}

type ProfileManager interface {
	GetRuneLimitByOwnerNameAndQuestionType(ownerName, qTypeName string) (int32, bool)
	GetFlightTimeByOwnerNameAndQuestionType(ownerName, qTypeName string) (time.Time, time.Time, bool)
	IsImageSupportedByOwnerNameAndQuestionType(ownerName, qTypeName string) bool
}

type TempFileRepo interface {
	GenerateTempFileID() (string, error)
	StoreTempFileChunk(id string, reader io.Reader) error
	RemoveTempFileByIdentifier(id string) error
	GetTempFilePathByID(id string) string
}

type PersistFileRepo interface {
	GetPresignedURL(ctx context.Context, key string) (*url.URL, error)
	Upload(ctx context.Context, key string, filepath string) error
}
