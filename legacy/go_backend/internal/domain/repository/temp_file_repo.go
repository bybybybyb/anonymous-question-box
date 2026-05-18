package repository

import (
	"io"
	"io/ioutil"
	"log"
	"os"
	"sync"

	"github.com/google/uuid"
)

type LocalTempFileRepo struct {
	RootDir       string
	IDToLocalPath map[string]string
	Mutex         *sync.Mutex
}

func (l *LocalTempFileRepo) GenerateTempFileID() string {
	return uuid.New().String()
}

func (l *LocalTempFileRepo) StoreTempFile(id, filename string, file io.Reader) error {
	tmpFile, err := os.CreateTemp(l.RootDir, "qboxTemp*")
	if err != nil {
		return err
	}
	buf, err := ioutil.ReadAll(file)
	if err != nil {
		return err
	}
	_, err = tmpFile.Write(buf)
	if err != nil {
		return err
	}
	l.Mutex.Lock()
	defer l.Mutex.Unlock()
	l.IDToLocalPath[id] = tmpFile.Name()
	return nil
}

func (l *LocalTempFileRepo) RemoveTempFileByID(id string) error {
	l.Mutex.Lock()
	defer l.Mutex.Unlock()
	if path, ok := l.IDToLocalPath[id]; ok {
		delete(l.IDToLocalPath, id)
		return os.Remove(path)
	}
	log.Printf("file id %s not found, ignored\n", id)
	return nil
}

func (l *LocalTempFileRepo) GetTempFilePathByID(id string) (string, bool) {
	l.Mutex.Lock()
	defer l.Mutex.Unlock()
	path, ok := l.IDToLocalPath[id]
	return path, ok
}
