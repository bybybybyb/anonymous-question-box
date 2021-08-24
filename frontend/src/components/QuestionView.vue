<template>
  <div>
    <Header :hideBackBtn="true"></Header>
    <div v-if="just_submitted">
      <QuestionSubmission :token="token" />
      <QuestionDisplay
        :receiver="receiver"
        :question_text="question_text"
        :asked_at="asked_at"
        :answer_text="answer_text"
        :answered_at="answered_at"
      />
    </div>
    <div v-else>
      <QuestionDisplay
        :receiver="receiver"
        :question_text="question_text"
        :asked_at="asked_at"
        :answer_text="answer_text"
        :answered_at="answered_at"
      />
      <QuestionSubmission :token="token" />
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
import QuestionDisplay from "./QuestionDisplay.vue";
import QuestionSubmission from "./QuestionSubmission.vue";
let currentBgClass = "";
export default {
  name: "QuestionView",
  props: {
    just_submitted: Boolean,
  },
  components: {
    Header,
    QuestionDisplay,
    QuestionSubmission,
  },
  created() {
    this.token = this.$route.query.token;
    const authHeader = {
      headers: { Authorization: `Bearer ${this.token}` },
    };
    this.axios
      .get("/api/questions/question", authHeader)
      .then((resp) => {
        this.owner = resp.data.owner;
        this.type = resp.data.type;
        this.receiver =
          this.ownerProfiles[this.owner].question_types[this.type].description;
        this.question_text = resp.data.text;
        this.asked_at = resp.data.asked_at;
        this.answer_text = resp.data.answer;
        this.answered_at = resp.data.answered_at;

        currentBgClass =
          this.ownerProfiles[this.owner].question_types[this.type].theme
            .background_class;
        document.body.classList.remove("bg-light");
        document.body.classList.add("body-background-" + currentBgClass);
        if (currentBgClass.includes("dark")) {
          this.card_background_style = "background: rgba(120,120,120,0.9)";
        }
      })
      .catch((err) => {
        if (err.response.status === 401 || err.response.status === 404) {
          alert("对不起，未能找到您的投稿。");
        } else {
          alert("提问箱好像坏掉了，请通知管理员前来查看！");
        }
        this.$router.push({ path: "/" });
      });
  },
  beforeUnmount() {
    // change back the body background
    document.body.classList.remove("body-background-" + currentBgClass);
    document.body.classList.add("bg-light");
  },
  data() {
    return {
      token: "",
      receiver: "",
      type: "",
      question_text: "",
      asked_at: "",
      answer_text: "",
      answered_at: "",
    };
  },
};
</script>