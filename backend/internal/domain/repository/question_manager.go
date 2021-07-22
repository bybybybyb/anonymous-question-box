package repository

import (
	"context"
	"database/sql"
	"fmt"
	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/anonymous-question-box/internal/infrastructure"
	"time"
)

type SQLiteQuestionManager struct{}

func (q *SQLiteQuestionManager) GetQuestionByUUID(ctx context.Context, uuid string) (*model.Question, error) {
	var id int32
	var askedAt int64
	var answeredAt sql.NullInt64
	var qOwner, qType, question string
	var answer sql.NullString

	err := infrastructure.DBConn.QueryRowContext(ctx, "SELECT `id`, `owner`, `type`, `question`, `answer`, `asked_at`, `answered_at` FROM `question` WHERE `uuid` = ? AND `deleted` = 0;",
		uuid).Scan(&id, &qOwner, &qType, &question, &answer, &askedAt, &answeredAt)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("question not found")
		}
		return nil, err
	}

	return &model.Question{
		ID:         id,
		UUID:       uuid,
		Owner:      qOwner,
		Type:       qType,
		Text:       question,
		AnswerText: answer.String,
		AskedAt:    time.Unix(askedAt, 0),
		AnsweredAt: time.Unix(answeredAt.Int64, 0),
	}, nil
}

func (q *SQLiteQuestionManager) ListQuestions(ctx context.Context, qOwner, qType, orderBy string, rowsPerPage, page int) ([]*model.Question, error) {
	questions := make([]*model.Question, 0)
	var id int32
	var askedAt int64
	var answeredAt sql.NullInt64
	var uuid, question string
	var answer sql.NullString

	rows, err := infrastructure.DBConn.QueryContext(ctx, "SELECT `id`, `uuid`, `question`, `answer`, `asked_at`, `answered_at` FROM `question` WHERE `owner` = ? AND `type` = ? AND `deleted` = 0 ORDER BY ? LIMIT ? OFFSET ?;",
		qOwner, qType, orderBy, rowsPerPage, rowsPerPage*(page-1))

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("no more questions")
		}
		return nil, err
	}

	for rows.Next() {
		rows.Scan(&id, &uuid, &question, &answer, &askedAt, &answeredAt)
		questions = append(questions, &model.Question{
			ID:         id,
			UUID:       uuid,
			Owner:      qOwner,
			Type:       qType,
			Text:       question,
			AnswerText: answer.String,
			AskedAt:    time.Unix(askedAt, 0),
			AnsweredAt: time.Unix(answeredAt.Int64, 0),
		})
	}
	return questions, nil
}

func (q *SQLiteQuestionManager) InsertQuestion(ctx context.Context, question *model.Question) error {
	result, err := infrastructure.DBConn.ExecContext(ctx, "INSERT INTO `question` (`uuid`, `owner`, `type`, `question`, `asked_at`) VALUES (?,?,?,?,?);",
		question.UUID, question.Owner, question.Type, question.Text, question.AskedAt.Unix())
	if err != nil {
		return err
	}
	id, err := result.LastInsertId()
	if err != nil {
		return err
	}
	if id <= 0 {
		return fmt.Errorf("failed to insert new question %s, reason unknown", question.UUID)
	}
	return nil
}
func (q *SQLiteQuestionManager) UpdateAnswer(ctx context.Context, question *model.Question) error {
	result, err := infrastructure.DBConn.ExecContext(ctx, "UPDATE `question` SET `answer` = ?, `answered_at` = ? WHERE `uuid` = ?",
		question.AnswerText, question.AnsweredAt.Unix(), question.UUID)
	if err != nil {
		return err
	}
	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return err
	}
	if rowsAffected != 1 {
		return fmt.Errorf("failed to update answer for question %s, reason unknown", question.UUID)
	}
	return nil
}
func (q *SQLiteQuestionManager) MarkAsDeleted(ctx context.Context, question *model.Question) error {
	result, err := infrastructure.DBConn.ExecContext(ctx, "UPDATE `question` SET `deleted` = 1 WHERE `uuid` = ?", question.UUID)
	if err != nil {
		return err
	}
	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return err
	}
	if rowsAffected != 1 {
		return fmt.Errorf("failed to mark question %s as deleted, reason unknown", question.UUID)
	}
	return nil
}
