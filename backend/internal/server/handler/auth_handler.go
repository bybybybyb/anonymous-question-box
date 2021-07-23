package handler

import (
	"fmt"
	"github.com/anonymous-question-box/internal/domain/repository"
	"github.com/gin-gonic/gin"
	"net/http"
	"strings"
)

type AuthHandler struct {
	TokenManager repository.TokenManager
}

func (a *AuthHandler) Authenticate(c *gin.Context) {
	var token string
	splits := strings.Split(c.GetHeader("Authorization"), "Bearer ")
	if len(splits) == 2 {
		token = splits[1]
	} else {
		c.AbortWithStatusJSON(http.StatusForbidden, ErrorResp{Error: "无效token"})
		return
	}
	uuid, isAdmin, err := a.TokenManager.ValidateToken(c, token)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusUnauthorized, ErrorResp{Error: fmt.Sprintf("无法解析token，错误信息：%s", err.Error())})
		return
	}
	c.Set("is_admin", isAdmin)
	c.Set("uuid", uuid)
}

func (a *AuthHandler) AuthorizeOwner(c *gin.Context) {
	if !c.GetBool("is_admin") {
		c.AbortWithStatusJSON(http.StatusUnauthorized, ErrorResp{Error: "未授权访问"})
	}
}

func (a *AuthHandler) BlockOwner(c *gin.Context) {
	if c.GetBool("is_admin") {
		c.AbortWithStatusJSON(http.StatusForbidden, ErrorResp{Error: "提问箱主人能问自己和其他提问箱主人问题嘛？答案是不能"})
		return
	}
}
