<template>
  <div>
    <div class="container">
      <div class="row">
        <div class="col-12 col-md-6">
          <div class="card my-3">
            <div class="card-body">
              <i class="my-3">提交时间：{{ formatTime(asked_at) }}</i>
              <ul class="list-unstyled mx-3 my-3" style="line-break: anywhere">
                <li
                  v-for="(sentence, i) in formatText(question_text)"
                  v-bind:key="i"
                >
                  {{ sentence }}
                </li>
              </ul>
            </div>
          </div>
        </div>
        <div class="col-12 col-md-6">
          <div class="card my-3">
            <div class="card-body">
              <i class="my-3">回复时间： {{ formatTime(answered_at) }}</i>
              <ul class="list-unstyled mx-3 my-3" style="line-break: anywhere">
                <li
                  v-for="(sentence, i) in formatText(answer_text)"
                  v-bind:key="i"
                >
                  {{ sentence }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "QuestionDisplay",
  props: {
    token: String,
  },
  computed: {
    formatTime() {
      return (timeStr) => {
        let time = Date.parse(timeStr);
        if (time === 0) {
          return "尚未回复，请耐心等待哦。";
        }
        return new Date(timeStr).toLocaleString();
      };
    },
    formatText() {
      return (text) => {
        return text.split(/(?:\r\n|\r|\n)/g);
      };
    },
  },
  beforeCreate() {
    const authHeader = {
      headers: { Authorization: `Bearer ${this.token}` },
    };
    this.axios
      .get("/api/questions/question", authHeader)
      .then((resp) => {
        this.question_text = resp.data.text;
        this.asked_at = resp.data.asked_at;
        this.answer_text = resp.data.answer;
        this.answered_at = resp.data.answered_at;
      })
      .catch((err) => {
        if (err.response.status === 401) {
          alert("对不起，未能找到您的投稿。");
        } else {
          alert("提问箱好像坏掉了，请通知管理员前来查看！");
        }
        this.$router.push({ path: "/" });
      });
  },
  data() {
    return {
      question_text: "",
      asked_at: "",
      answer_text: "",
      answered_at: "",
    };
  },
};
</script>
