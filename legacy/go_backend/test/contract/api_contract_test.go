package contract

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/anonymous-question-box/internal/infrastructure"
	"github.com/anonymous-question-box/internal/server"
	"github.com/golang-jwt/jwt"
	"github.com/spf13/viper"
)

const jwtSecret = "contract-secret"
const magicSpell = "spell"

func setupContractServer(t *testing.T) (*httptest.Server, func()) {
	t.Helper()
	viper.Reset()
	tmp := t.TempDir()
	schemaBytes, err := os.ReadFile(filepath.Join("..", "..", "..", "schema", "question.sql"))
	if err != nil {
		t.Fatalf("read schema: %v", err)
	}
	dbPath := filepath.Join(tmp, "contract.sqlite3")
	viper.Set("db_path", dbPath)
	viper.Set("db_max_connections", 1)
	viper.Set("jwt_secret_key", jwtSecret)
	viper.Set("magic_spell", magicSpell)
	viper.Set("filtered_keywords", []string{"blocked"})
	viper.Set("temp_file_root_dir", tmp)
	viper.Set("oss_url", "http://cos.example.com")
	viper.Set("oss_cdn_url", "http://cdn.example.com")
	viper.Set("oss_bucket", "bucket")
	viper.Set("default_rune_limit", 500)
	viper.Set("owner_profiles", []map[string]interface{}{
		{
			"name": "owner",
			"colors": map[string]string{
				"primary_color":   "#111",
				"secondary_color": "#eee",
			},
			"question_types": map[string]interface{}{
				"type": map[string]interface{}{
					"name":          "type",
					"description":   "Type",
					"rune_limit":    20,
					"support_image": false,
					"theme": map[string]string{
						"name":             "theme",
						"background_class": "bg",
					},
				},
			},
		},
	})

	if err := infrastructure.InitSQLiteDB(); err != nil {
		t.Fatalf("init db: %v", err)
	}
	if _, err := infrastructure.DBConn.Exec(string(schemaBytes)); err != nil {
		t.Fatalf("apply schema: %v", err)
	}
	if err := infrastructure.LoadProfiles(); err != nil {
		t.Fatalf("load profiles: %v", err)
	}
	router, exit, wg := server.SetupRoutes()
	ts := httptest.NewServer(router)
	return ts, func() {
		ts.Close()
		exit <- true
		wg.Wait()
		_ = infrastructure.DBConn.Close()
	}
}

func adminToken(t *testing.T) string {
	t.Helper()
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		magicSpell: "admin-session",
		"iat":      time.Now().Unix(),
		"exp":      time.Now().Add(time.Hour).Unix(),
	})
	encoded, err := token.SignedString([]byte(jwtSecret))
	if err != nil {
		t.Fatalf("sign admin token: %v", err)
	}
	return encoded
}

func getUserToken(t *testing.T, baseURL string) string {
	t.Helper()
	resp, err := http.Get(baseURL + "/new")
	if err != nil {
		t.Fatalf("new token: %v", err)
	}
	defer resp.Body.Close()
	var tokenResp struct {
		Token string `json:"token"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		t.Fatalf("decode token: %v", err)
	}
	return tokenResp.Token
}

func doReq(t *testing.T, method, url, token string, body []byte) (int, []byte) {
	t.Helper()
	var reader io.Reader
	if body != nil {
		reader = bytes.NewReader(body)
	}
	req, err := http.NewRequest(method, url, reader)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("%s %s: %v", method, url, err)
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read response: %v", err)
	}
	return resp.StatusCode, respBody
}

func assertError(t *testing.T, body []byte, want string) {
	t.Helper()
	var parsed struct {
		Error string `json:"error"`
	}
	if err := json.Unmarshal(body, &parsed); err != nil {
		t.Fatalf("decode error body: %v", err)
	}
	if parsed.Error != want {
		t.Fatalf("error = %q, want %q", parsed.Error, want)
	}
}

func TestProfilesAndAuthContract(t *testing.T) {
	ts, cleanup := setupContractServer(t)
	defer cleanup()

	resp, err := http.Get(ts.URL + "/profiles")
	if err != nil {
		t.Fatalf("profiles: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("profiles status = %d, want 200", resp.StatusCode)
	}
	var profiles struct {
		OwnerProfiles map[string]struct {
			QuestionTypes map[string]struct {
				SupportImage bool `json:"support_image"`
			} `json:"question_types"`
		} `json:"owner_profiles"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&profiles); err != nil {
		t.Fatalf("decode profiles: %v", err)
	}
	if profiles.OwnerProfiles["owner"].QuestionTypes["type"].SupportImage {
		t.Fatal("profile support_image = true, want false")
	}

	status, body := doReq(t, http.MethodGet, ts.URL+"/questions/question", "", nil)
	if status != http.StatusForbidden {
		t.Fatalf("missing auth status = %d, want 403", status)
	}
	assertError(t, body, "无效token")

	userToken := getUserToken(t, ts.URL)
	status, body = doReq(t, http.MethodPost, ts.URL+"/owner/questions", userToken, []byte(`{}`))
	if status != http.StatusUnauthorized {
		t.Fatalf("user owner route status = %d, want 401", status)
	}
	assertError(t, body, "未授权访问")

	status, body = doReq(t, http.MethodPost, ts.URL+"/questions/submit", adminToken(t), []byte(`{}`))
	if status != http.StatusForbidden {
		t.Fatalf("admin submit status = %d, want 403", status)
	}
	assertError(t, body, "提问箱主人能问自己和其他提问箱主人问题嘛？答案是不能")
}

func TestSubmitValidationContract(t *testing.T) {
	ts, cleanup := setupContractServer(t)
	defer cleanup()
	token := getUserToken(t, ts.URL)

	status, body := doReq(t, http.MethodPost, ts.URL+"/questions/submit", token, []byte(`{"owner":"owner","type":"type","text":"hello","images":[{"image_id":"x"}]}`))
	if status != http.StatusBadRequest {
		t.Fatalf("image submit status = %d, want 400", status)
	}
	assertError(t, body, "本提问箱不支持图片上传")

	status, body = doReq(t, http.MethodPost, ts.URL+"/questions/submit", token, []byte(`{"owner":"owner","type":"type","text":"    "}`))
	if status != http.StatusBadRequest {
		t.Fatalf("empty submit status = %d, want 400", status)
	}
	assertError(t, body, "空投稿")
}

func TestKeywordSoftDeleteContract(t *testing.T) {
	ts, cleanup := setupContractServer(t)
	defer cleanup()

	token := getUserToken(t, ts.URL)

	submitBody := []byte(`{"owner":"owner","type":"type","text":"blocked text"}`)
	status, _ := doReq(t, http.MethodPost, ts.URL+"/questions/submit", token, submitBody)
	if status != http.StatusOK {
		t.Fatalf("submit status = %d, want 200", status)
	}

	status, body := doReq(t, http.MethodGet, ts.URL+"/questions/question", token, nil)
	if status != http.StatusOK {
		t.Fatalf("asker read status = %d, want 200", status)
	}
	var read struct {
		AnsweredAt string `json:"answered_at"`
	}
	if err := json.Unmarshal(body, &read); err != nil {
		t.Fatalf("decode asker read: %v", err)
	}
	answeredAt, err := time.Parse(time.RFC3339, read.AnsweredAt)
	if err != nil {
		t.Fatalf("parse answered_at %q: %v", read.AnsweredAt, err)
	}
	if answeredAt.Unix() != 0 {
		t.Fatalf("answered_at = %q, want epoch instant", read.AnsweredAt)
	}

	listBody := []byte(`{"owner":"owner","type":"type","order_params":{"by":"asked_at","reversed":true},"day_limit":1,"page_size":10,"page":1}`)
	status, body = doReq(t, http.MethodPost, ts.URL+"/owner/questions", adminToken(t), listBody)
	if status != http.StatusOK {
		t.Fatalf("owner list status = %d, want 200", status)
	}
	var list struct {
		Total int `json:"total"`
	}
	if err := json.Unmarshal(body, &list); err != nil {
		t.Fatalf("decode list: %v", err)
	}
	if list.Total != 0 {
		t.Fatalf("soft-deleted keyword submission visible in owner list: total=%d", list.Total)
	}
}
