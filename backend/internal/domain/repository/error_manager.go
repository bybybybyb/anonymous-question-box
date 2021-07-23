package repository

type StatusError interface {
	Error() string
	Code() int
}

type AppError struct {
	error
	code int
}

func (a AppError) Code() int {
	return a.code
}

func E(err error, code int) AppError {
	return AppError{err, code}
}
