package repository

import (
	"context"
	"database/sql"
	"fmt"
	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/anonymous-question-box/internal/infrastructure"
	"net/http"
	"time"
	"unicode/utf8"
)

type SQLiteQuestionManager struct{}

func (q *SQLiteQuestionManager) GetQuestionByUUID(ctx context.Context, uuid string) (*model.Question, StatusError) {
	var id int32
	var askedAt int64
	var answeredAt sql.NullInt64
	var qOwner, qType, question string
	var answer sql.NullString

	err := infrastructure.DBConn.QueryRowContext(ctx, "SELECT `id`, `owner`, `question_type`, `question`, `answer`, `asked_at`, `answered_at` FROM `question` WHERE `uuid` = ? AND `deleted_at` IS NULL",
		uuid).Scan(&id, &qOwner, &qType, &question, &answer, &askedAt, &answeredAt)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, E(err, http.StatusNotFound)
		}
		return nil, E(err, http.StatusInternalServerError)
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

func (q *SQLiteQuestionManager) ListQuestions(ctx context.Context, qOwner, qType, orderBy string, orderReversed bool, due int64, rowsPerPage, page, replyStatus int32) ([]*model.Question, int32, StatusError) {
	questions := make([]*model.Question, 0)
	var id, wordCount, totalCount int32
	var askedAt int64
	var answeredAt sql.NullInt64
	var uuid, question string
	var answer sql.NullString

	// sorting & filters
	if orderBy == "" {
		orderBy = "asked_at"
	}
	direction := fmt.Sprintf("`%s` ASC", orderBy)
	if orderReversed {
		direction = fmt.Sprintf("`%s` DESC", orderBy)
	}
	replyFilterStr := ""
	if replyStatus < 0 {
		replyFilterStr = "AND answered_at IS NULL"
	} else if replyStatus > 0 {
		replyFilterStr = "AND answered_at IS NOT NULL"
	}

	attrs := "`id`, `uuid`, `question`, `word_count`, `answer`, `asked_at`, `answered_at`"
	counts := "COUNT(*)"

	sqlStr := buildQuery(counts, replyFilterStr, direction, false)
	row := infrastructure.DBConn.QueryRowContext(ctx, sqlStr, qOwner, qType, due)
	err := row.Scan(&totalCount)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, 0, E(err, http.StatusNotFound)
		}
		return nil, 0, E(err, http.StatusInternalServerError)
	}

	sqlStr = buildQuery(attrs, replyFilterStr, direction, true)
	rows, err := infrastructure.DBConn.QueryContext(ctx, sqlStr,
		qOwner, qType, due, rowsPerPage, rowsPerPage*(page-1))

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, 0, E(err, http.StatusNotFound)
		}
		return nil, 0, E(err, http.StatusInternalServerError)
	}

	for rows.Next() {
		rows.Scan(&id, &uuid, &question, &wordCount, &answer, &askedAt, &answeredAt)
		questions = append(questions, &model.Question{
			ID:         id,
			UUID:       uuid,
			Owner:      qOwner,
			Type:       qType,
			Text:       question,
			WordCount:  wordCount,
			AnswerText: answer.String,
			AskedAt:    time.Unix(askedAt, 0),
			AnsweredAt: time.Unix(answeredAt.Int64, 0),
		})
	}

	return questions, totalCount, nil
}

func (q *SQLiteQuestionManager) InsertQuestion(ctx context.Context, question *model.Question) StatusError {
	result, err := infrastructure.DBConn.ExecContext(ctx, "INSERT INTO `question` (`uuid`, `owner`, `question_type`, `question`, `word_count`, `asked_at`) VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING;",
		question.UUID, question.Owner, question.Type, question.Text, utf8.RuneCountInString(question.Text), question.AskedAt.Unix())
	if err != nil {
		return E(err, http.StatusInternalServerError)
	}
	id, err := result.LastInsertId()
	if err != nil {
		return E(err, http.StatusInternalServerError)
	}
	if id <= 0 {
		return E(fmt.Errorf("no row inserted"), http.StatusConflict)
	}
	return nil
}

func (q *SQLiteQuestionManager) UpdateAnswer(ctx context.Context, question *model.Question) StatusError {
	result, err := infrastructure.DBConn.ExecContext(ctx, "UPDATE `question` SET `answer` = ?, `answered_at` = ? WHERE `uuid` = ?",
		question.AnswerText, question.AnsweredAt.Unix(), question.UUID)
	if err != nil {
		return E(err, http.StatusInternalServerError)
	}
	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return E(err, http.StatusInternalServerError)
	}
	if rowsAffected != 1 {
		return E(err, http.StatusNotFound)
	}
	return nil
}

func (q *SQLiteQuestionManager) MarkAsDeleted(ctx context.Context, uuid string) StatusError {
	result, err := infrastructure.DBConn.ExecContext(ctx, "UPDATE `question` SET `deleted_at` = ? WHERE `uuid` = ?", time.Now().Unix(), uuid)
	if err != nil {
		return E(err, http.StatusInternalServerError)
	}
	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return E(err, http.StatusInternalServerError)
	}
	if rowsAffected != 1 {
		return E(err, http.StatusNotFound)
	}
	return nil
}

func buildQuery(toSelect, filter, direction string, withPagination bool) string {
	sqlStr := "SELECT " + toSelect + " FROM `question` WHERE `owner` = ? AND `question_type` = ? AND `asked_at` > ? AND `deleted_at` IS NULL " + filter + " ORDER BY " + direction
	if withPagination {
		sqlStr += " LIMIT ? OFFSET ?;"
	}
	return sqlStr
}
