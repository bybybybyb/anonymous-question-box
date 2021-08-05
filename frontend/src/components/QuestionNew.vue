<template>
  <div>
    <Header :hideBackBtn="true"></Header>
    <div>
      <div class="container">
        <div class="card my-3 shadow-lg" :style="cardBackgroundStyle">
          <div class="card-body">
            <div class="row">
              <div class="col-4">
                <h5 :style="h5Style">收件人：</h5>
              </div>
              <div class="col-8">
                <select
                  class="form-select form-select-sm"
                  :class="formStyleClass"
                  aria-label="Default select example"
                  id="question_type"
                  v-on:change="onReceiverChange"
                  v-model="type"
                >
                  <option
                    v-for="q_type in ownerProfiles[owner].question_types"
                    v-bind:key="q_type.name"
                    :value="q_type.name"
                  >
                    {{ q_type.description }}
                  </option>
                </select>
              </div>
            </div>
          </div>
        </div>
        <div class="card my-3 shadow-lg" v-bind:style="cardBackgroundStyle">
          <div class="card-body">
            <textarea
              class="col-12 form-control"
              rows="20"
              :class="formStyleClass"
              v-model="new_question_text"
              :maxlength="maxLength"
              v-on:keyup="onNewInput"
            ></textarea>
            <h5 class="col-12 m-1" :style="h5Style">
              当前字数： {{ currentLength }}/{{ maxLength }}
            </h5>
            <button
              class="btn col-sm-5 col-12"
              :class="[submitBtnActiveClass, submitBtnStyleClass]"
              v-on:click="submit"
            >
              提交
            </button>
            <h5 class="col-12 m-2" :style="h5Style">
              小提示：尚未成功提交的草稿将被暂存于您的浏览器储存中。
            </h5>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
const storagePrefix = "questionNew_";
let prevBgClass = "";
export default {
  name: "QuestionNew",
  components: {
    Header,
  },
  props: {
    owner: String,
  },
  methods: {
    onNewInput() {
      this.currentLength = this.new_question_text.length;
      localStorage.setItem(storagePrefix + "draft", this.new_question_text);
      this.currentLength > 0
        ? (this.submitBtnActiveClass = "")
        : (this.submitBtnActiveClass = "disabled");
    },
    onReceiverChange(event) {
      this.maxLength =
        this.ownerProfiles[this.owner].question_types[
          event.target.value
        ].rune_limit;

      // style changes
      // body background
      let newBgClass =
        this.ownerProfiles[this.owner].question_types[event.target.value]
          .background_class;
      document.body.classList.remove("body-background-" + prevBgClass);
      document.body.classList.add("body-background-" + newBgClass);
      prevBgClass = newBgClass;
      // card background
      if (newBgClass.includes("dark")) {
        this.cardBackgroundStyle = "background: rgba(120,120,120,0.7)";
        this.h5Style = "color:white";
        this.submitBtnStyleClass = "btn-success";
        this.formStyleClass = "bg-dark text-light";
      } else {
        this.cardBackgroundStyle = "background: rgba(255,255,255,0.7)";
        this.h5Style = "color:black";
        this.submitBtnStyleClass = "btn-outline-success";
        this.formStyleClass = "bg-light text-dark";
      }
    },
    submit() {
      const authHeader = {
        headers: { Authorization: `Bearer ${this.token}` },
      };
      this.axios
        .post(
          "/api/questions/submit",
          {
            owner: this.owner,
            type: this.type,
            text: this.new_question_text,
          },
          authHeader
        )
        .then(() => {
          localStorage.setItem(storagePrefix + "draft", "");
          this.$router.push({
            name: "question",
            query: { token: this.token },
            params: { just_submitted: true },
          });
        })
        .catch((err) => {
          alert("提问箱好像坏掉了，请保存好您的投稿，并通知管理员前来查看！");
          console.log(err.response);
        });
    },
  },
  beforeMount() {
    // change body background
    document.body.classList.remove("bg-light");
    let newBgClass =
      this.ownerProfiles[this.owner].question_types[this.type].background_class;
    document.body.classList.add("body-background-" + newBgClass);
    prevBgClass = newBgClass;

    let localVal = localStorage.getItem(storagePrefix + "draft");
    if (localVal && localVal !== "") {
      this.new_question_text = localVal;
      this.onNewInput();
    }
    this.axios
      .get("/api/new")
      .then((resp) => {
        this.token = resp.data.token;
      })
      .catch((err) => {
        alert("提问箱好像坏掉了，请保存好您的投稿，并通知管理员前来查看！");
        console.log(err.response);
      });
  },
  beforeUnmount() {
    // change back the body background
    document.body.classList.remove("body-background-" + prevBgClass);
    document.body.classList.add("bg-light");
  },
  data() {
    return {
      type: "normal",
      token: "",
      question_text: "",
      asked_at: "",
      answer_text: "",
      answered_at: "",
      new_question_text: "",
      currentLength: 0,
      maxLength: 500,
      submitBtnActiveClass: "disabled",
      submitBtnStyleClass: "btn-outline-success",
      cardBackgroundStyle: "background: rgba(255,255,255,0.7)",
      formStyleClass: "bg-light text-dark",
      h5Style: "color:black",
    };
  },
};
</script>
