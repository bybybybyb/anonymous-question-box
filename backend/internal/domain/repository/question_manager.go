package repository

import (
	"context"
	"database/sql"
	"fmt"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/anonymous-question-box/internal/domain/model"
	"github.com/anonymous-question-box/internal/infrastructure"
)

type SQLiteQuestionManager struct{}

func (q *SQLiteQuestionManager) GetQuestionByUUID(ctx context.Context, uuid string, withVisitInfo bool) (*model.Question, StatusError) {
	var id, visitCount int32
	var askedAt, lastVisitedAt int64
	var answeredAt sql.NullInt64
	var qOwner, qType, question string
	var answer sql.NullString

	sqlStr := "SELECT `id`, `owner`, `question_type`, `question`, `answer`, `asked_at`, `answered_at` FROM `question` WHERE `uuid` = ? AND `deleted_at` IS NULL"
	err := infrastructure.DBConn.QueryRowContext(ctx, sqlStr, uuid).Scan(&id, &qOwner, &qType, &question, &answer, &askedAt, &answeredAt)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, E(err, http.StatusNotFound)
		}
		return nil, E(err, http.StatusInternalServerError)
	}

	if withVisitInfo {
		sqlStr = "SELECT `last_visited_at`, `visit_count` FROM `visit` WHERE `uuid` = ?"
		err = infrastructure.DBConn.QueryRowContext(ctx, sqlStr, uuid).Scan(&lastVisitedAt, &visitCount)
		if err != nil {
			if err != sql.ErrNoRows {
				return nil, E(err, http.StatusInternalServerError)
			}
		}
	}

	return &model.Question{
		ID:            id,
		UUID:          uuid,
		Owner:         qOwner,
		Type:          qType,
		Text:          question,
		AnswerText:    answer.String,
		AskedAt:       time.Unix(askedAt, 0),
		AnsweredAt:    time.Unix(answeredAt.Int64, 0),
		LastVisitedAt: time.Unix(lastVisitedAt, 0),
		VisitCount:    visitCount,
	}, nil
}

func (q *SQLiteQuestionManager) ListQuestions(ctx context.Context, qOwner, qType, orderBy string, orderReversed bool, due int64, rowsPerPage, page, replyStatus int32) ([]*model.Question, int32, StatusError) {
	questions := make([]*model.Question, 0)
	var totalCount int32
	// sorting & filters
	if orderBy == "" {
		orderBy = "q.`asked_at`"
	}
	direction := fmt.Sprintf("`%s` ASC", orderBy)
	if orderReversed {
		direction = fmt.Sprintf("`%s` DESC", orderBy)
	}
	replyFilterStr := ""
	if replyStatus < 0 {
		replyFilterStr = "AND q.`answered_at` IS NULL"
	} else if replyStatus == 1 {
		replyFilterStr = "AND q.`answered_at` IS NOT NULL"
	} else if replyStatus == 2 {
		replyFilterStr = "AND q.`answered_at` IS NOT NULL AND q.`answered_by` = 'manual'"
	}

	attrs := "q.`id`, q.`uuid`, q.`question`, q.`word_count`, q.`answer`, q.`asked_at`, q.`answered_at`, q.`answered_by`, v.`last_visited_at`, v.`visit_count`"
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

	if totalCount == 0 {
		return questions, totalCount, nil
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
		var id, wordCount, visitCount int32
		var askedAt, lastVisitedAt int64
		var answeredAt sql.NullInt64
		var uuid, question string
		var answer, answeredBy sql.NullString
		rows.Scan(&id, &uuid, &question, &wordCount, &answer, &askedAt, &answeredAt, &answeredBy, &lastVisitedAt, &visitCount)
		questions = append(questions, &model.Question{
			ID:            id,
			UUID:          uuid,
			Owner:         qOwner,
			Type:          qType,
			Text:          question,
			WordCount:     wordCount,
			AnswerText:    answer.String,
			AskedAt:       time.Unix(askedAt, 0),
			AnsweredAt:    time.Unix(answeredAt.Int64, 0),
			AnsweredBy:    answeredBy.String,
			LastVisitedAt: time.Unix(lastVisitedAt, 0),
			VisitCount:    visitCount,
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
	result, err := infrastructure.DBConn.ExecContext(ctx, "UPDATE `question` SET `answer` = ?, `answered_at` = ?, `answered_by` = ? WHERE `uuid` = ?",
		question.AnswerText, question.AnsweredAt.Unix(), question.AnsweredBy, question.UUID)
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

func (q *SQLiteQuestionManager) RecordVisit(ctx context.Context, perQuestionVisitMap map[string]*model.VisitStatus) StatusError {
	uuids := make([]interface{}, 0)
	placeholders := make([]string, 0)
	for uuid := range perQuestionVisitMap {
		uuids = append(uuids, uuid)
		placeholders = append(placeholders, "?")
	}
	querySql := fmt.Sprintf("SELECT `uuid`, `visit_count` FROM `visit` WHERE `uuid` IN (%s)", strings.Join(placeholders, ","))
	rows, err := infrastructure.DBConn.QueryContext(ctx, querySql, uuids...)

	if err != nil {
		if err != sql.ErrNoRows {
			return E(err, http.StatusInternalServerError)
		}
	}

	prevVisitStatus := make(map[string]*model.VisitStatus)
	for rows.Next() {
		var uuid string
		var visitCount int32
		rows.Scan(&uuid, &visitCount)
		status, ok := prevVisitStatus[uuid]
		if !ok {
			status = &model.VisitStatus{}
		}
		status.UUID = uuid
		status.VisitCount = visitCount
		prevVisitStatus[status.UUID] = status
	}

	insertValStrs := []string{}
	insertVals := []interface{}{}
	updateValStrs := []string{}
	updateVals := []interface{}{}
	for uuid := range perQuestionVisitMap {
		if prevStatus, ok := prevVisitStatus[uuid]; ok {
			perQuestionVisitMap[uuid].VisitCount += prevStatus.VisitCount
			updateValStrs = append(updateValStrs, "UPDATE `visit` SET `last_visited_at` = ?, `visit_count` = ? WHERE `uuid` = ?")
			updateVals = append(updateVals, perQuestionVisitMap[uuid].VisitedAt.Unix(), perQuestionVisitMap[uuid].VisitCount, perQuestionVisitMap[uuid].UUID)
		} else {
			insertValStrs = append(insertValStrs, "(?, ?, ?)")
			insertVals = append(insertVals, perQuestionVisitMap[uuid].UUID, perQuestionVisitMap[uuid].VisitedAt.Unix(), perQuestionVisitMap[uuid].VisitCount)
		}
	}

	if len(insertVals) > 0 {
		insertSql := "INSERT INTO `visit` (`uuid`, `last_visited_at`, `visit_count`) VALUES " + strings.Join(insertValStrs, ", ")
		_, err = infrastructure.DBConn.ExecContext(ctx, insertSql, insertVals...)
		if err != nil {
			return E(err, http.StatusInternalServerError)
		}
	}

	if len(updateVals) > 0 {
		updateSql := strings.Join(updateValStrs, "; ")
		_, err = infrastructure.DBConn.ExecContext(ctx, updateSql, updateVals...)
		if err != nil {
			return E(err, http.StatusInternalServerError)
		}
	}
	return nil
}

func (q *SQLiteQuestionManager) GetImageMetadataByUUID(ctx context.Context, uuid string) ([]*model.ImageMetadata, StatusError) {
	rows, err := infrastructure.DBConn.QueryContext(ctx, "SELECT `key`, `filename`, `image_order` FROM `image` WHERE `uuid` = ?", uuid)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, E(err, http.StatusNotFound)
		}
		return nil, E(err, http.StatusInternalServerError)
	}
	images := make([]*model.ImageMetadata, 0)
	for rows.Next() {
		var key, filename string
		var order int32
		rows.Scan(&key, &filename, &order)
		images = append(images, &model.ImageMetadata{Key: key, Filename: filename, Order: order})
	}
	return images, nil
}

func (q *SQLiteQuestionManager) StoreImageMetadata(ctx context.Context, imageMetadata []*model.ImageMetadata) StatusError {
	insertValStrs := []string{}
	insertVals := []interface{}{}
	for _, image := range imageMetadata {
		insertValStrs = append(insertValStrs, "(?, ?, ?, ?)")
		insertVals = append(insertVals, image.QuestionUUID, image.Key, image.Filename, image.Order)
	}
	if len(insertVals) > 0 {
		insertSql := "INSERT INTO `image` (`uuid`, `key`, `filename`, `image_order`) VALUES " + strings.Join(insertValStrs, ", ")
		_, err := infrastructure.DBConn.ExecContext(ctx, insertSql, insertVals...)
		if err != nil {
			return E(err, http.StatusInternalServerError)
		}
	}
	return nil
}

func buildQuery(toSelect, filter, direction string, getValue bool) string {
	sqlStr := "SELECT " + toSelect + " FROM `question` q "
	if getValue {
		sqlStr += "LEFT OUTER JOIN `visit` v ON v.`uuid` = q.`uuid` "
	}

	sqlStr += "WHERE q.`owner` = ? AND q.`question_type` = ? AND q.`asked_at` > ? AND q.`deleted_at` IS NULL " + filter + " ORDER BY " + direction
	if getValue {
		sqlStr += " LIMIT ? OFFSET ?;"
	}
	return sqlStr
}
