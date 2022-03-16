package repository

import (
	"context"
	"net/http"
	"net/url"
	"time"

	"github.com/tencentyun/cos-go-sdk-v5"
)

func NewTencentOSSPersistFileRepo(url *url.URL, accessID, accessKey, bucket string) *TencentOSSPersistFileRepo {
	client := cos.NewClient(
		&cos.BaseURL{BucketURL: url},
		&http.Client{
			Transport: &cos.AuthorizationTransport{
				SecretID:  accessID,
				SecretKey: accessKey,
			},
		},
	)
	return &TencentOSSPersistFileRepo{
		client: client,
		Bucket: bucket,
		ID:     accessID,
		Key:    accessKey,
	}
}

type TencentOSSPersistFileRepo struct {
	client *cos.Client
	Bucket string
	ID     string
	Key    string
}

func (t *TencentOSSPersistFileRepo) GetPresignedURL(ctx context.Context, key string) (*url.URL, error) {
	return t.client.Object.GetPresignedURL(ctx, http.MethodGet, key, t.ID, t.Key, time.Hour*12, nil)
}
func (t *TencentOSSPersistFileRepo) Upload(ctx context.Context, key string, filepath string) error {
	_, _, err := t.client.Object.Upload(ctx, key, filepath, nil)
	return err
}
