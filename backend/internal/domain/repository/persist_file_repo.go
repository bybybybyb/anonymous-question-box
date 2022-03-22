package repository

import (
	"context"
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/url"
	"time"

	"github.com/tencentyun/cos-go-sdk-v5"
)

func NewTencentOSSPersistFileRepo(bucketURLStr, cdnURLStr, accessID, accessKey, cdnKey, bucket string) (*TencentOSSPersistFileRepo, error) {
	bucketURL, err := url.Parse(bucketURLStr)
	if err != nil {
		return nil, err
	}
	client := cos.NewClient(
		&cos.BaseURL{BucketURL: bucketURL},
		&http.Client{
			Transport: &cos.AuthorizationTransport{
				SecretID:  accessID,
				SecretKey: accessKey,
			},
		},
	)
	return &TencentOSSPersistFileRepo{
		client:    client,
		bucketURL: bucketURL,
		cdnURL:    cdnURLStr,
		bucket:    bucket,
		secretID:  accessID,
		secretKey: accessKey,
		cdnKey:    cdnKey,
	}, nil
}

type TencentOSSPersistFileRepo struct {
	client    *cos.Client
	bucketURL *url.URL
	cdnURL    string
	bucket    string
	secretID  string
	secretKey string
	cdnKey    string
}

func (t *TencentOSSPersistFileRepo) GetPresignedURL(ctx context.Context, path string) (*url.URL, error) {
	// return t.client.Object.GetPresignedURL(ctx, http.MethodGet, key, t.secretID, t.secretKey, time.Hour*12, nil)
	now := time.Now().Unix()
	if path[0] != '/' {
		path = "/" + path
	}
	sign := md5.Sum([]byte(fmt.Sprintf("%s%s%d", t.cdnKey, path, now)))
	signedURL := fmt.Sprintf("%s%s?%s=%s&%s=%d", t.cdnURL, path, "sign", hex.EncodeToString(sign[:]), "t", now)
	return url.ParseRequestURI(signedURL)
}
func (t *TencentOSSPersistFileRepo) Upload(ctx context.Context, key string, filepath string) error {
	_, _, err := t.client.Object.Upload(ctx, key, filepath, nil)
	return err
}
