<template>
  <Header :hideBackBtn="true"></Header>
  <div class="container">
    <div class="row">
      <div class="col-12" :class="justSubmitted ? 'order-1' : 'order-2'">
        <QuestionSubmission :token="token" />
      </div>
      <div class="col-12" :class="justSubmitted ? 'order-2' : 'order-1'">
        <QuestionDisplay
          :receiver="receiver"
          :question_text="question_text"
          :asked_at="asked_at"
          :answer_text="answer_text"
          :answered_at="answered_at"
          :images="images"
        />
      </div>
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
    justSubmitted: Boolean,
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
        this.images = resp.data.images;

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
      images: [],
    };
  },
};
</script>
