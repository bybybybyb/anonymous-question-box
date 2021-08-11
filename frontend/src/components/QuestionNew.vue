<template>
  <div>
    <Header :hideBackBtn="true"></Header>
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
            class="col-12 form-control overflow-auto"
            rows="15"
            :class="formStyleClass"
            v-model="new_question_text"
            :maxlength="maxLength"
            v-on:keyup="onNewInput"
            v-on:input="onNewInput"
          ></textarea>
          <h5 class="col-12 m-1" :style="h5Style">
            当前字数： {{ currentLength }}/{{ maxLength }}
          </h5>
          <button
            class="btn col-sm-5 col-12"
            :class="[submitBtnActiveClass, submitBtnStyleClass]"
            data-bs-toggle="modal"
            data-bs-target="#submitConfirmModal"
          >
            提交
          </button>
          <h5 class="col-12 m-2" :style="h5Style">
            小提示：尚未成功提交的草稿将被暂存于您的浏览器储存中。
          </h5>
        </div>
      </div>
    </div>
    <div
      class="modal fade"
      id="submitConfirmModal"
      tabindex="-1"
      aria-labelledby="submitConfirmModalLabel"
      aria-hidden="true"
    >
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content" :class="formStyleClass">
          <div class="modal-header">
            <h5 class="modal-title" id="submitConfirmModalLabel">确认提交？</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            提交后将无法进行更改，建议再读一遍检查一下哦？
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn"
              :class="dismissBtnStyleClass"
              data-bs-dismiss="modal"
            >
              再看一眼
            </button>
            <button
              type="button"
              class="btn"
              :class="confirmBtnStyleClass"
              v-on:click="submit"
              data-bs-dismiss="modal"
            >
              确认提交
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
const storagePrefix = "questionNew_";
let currentQuestionTypePrefix = "";
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
      localStorage.setItem(
        storagePrefix + currentQuestionTypePrefix + "draft",
        this.new_question_text
      );
      this.currentLength > 0
        ? (this.submitBtnActiveClass = "")
        : (this.submitBtnActiveClass = "disabled");
    },
    onReceiverChange(event) {
      this.maxLength =
        this.ownerProfiles[this.owner].question_types[
          event.target.value
        ].rune_limit;
      currentQuestionTypePrefix = "_" + [this.owner, this.type].join("_") + "_";
      let localVal = localStorage.getItem(
        storagePrefix + currentQuestionTypePrefix + "draft"
      );
      if (localVal && localVal !== "") {
        this.new_question_text = localVal;
      } else {
        this.new_question_text = "";
      }
      this.onNewInput();

      // style changes
      // body background
      let newBgClass =
        this.ownerProfiles[this.owner].question_types[event.target.value].theme
          .background_class;
      document.body.classList.remove("body-background-" + prevBgClass);
      document.body.classList.add("body-background-" + newBgClass);
      prevBgClass = newBgClass;
      // card background
      if (newBgClass.includes("dark")) {
        this.cardBackgroundStyle = "background: rgba(120,120,120,0.9)";
        this.h5Style = "color:white";
        this.submitBtnStyleClass = "btn-success";
        this.dismissBtnStyleClass = "btn-secondary";
        this.confirmBtnStyleClass = "btn-danger";
        this.formStyleClass = "bg-dark text-light";
      } else {
        this.cardBackgroundStyle = "background: rgba(255,255,255,0.9)";
        this.h5Style = "color:black";
        this.submitBtnStyleClass = "btn-outline-success";
        this.dismissBtnStyleClass = "btn-outline-secondary";
        this.confirmBtnStyleClass = "btn-outline-danger";
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
          localStorage.setItem(
            storagePrefix + currentQuestionTypePrefix + "draft",
            ""
          );
          this.$router.push({
            name: "question",
            query: { token: this.token },
            params: { just_submitted: true },
          });
        })
        .catch((err) => {
          console.log(err.response);
          if (err.response.status === 400) {
            alert("您的投稿好像不太对劲？ " + err.response.data.error);
          } else {
            alert("提问箱好像坏掉了，请保存好您的投稿，并通知管理员前来查看！");
          }
        });
    },
  },
  beforeMount() {
    // change body background
    document.body.classList.remove("bg-light");
    let newBgClass =
      this.ownerProfiles[this.owner].question_types[this.type].theme
        .background_class;
    document.body.classList.add("body-background-" + newBgClass);
    prevBgClass = newBgClass;

    currentQuestionTypePrefix = "_" + [this.owner, this.type].join("_") + "_";
    let localVal = localStorage.getItem(
      storagePrefix + currentQuestionTypePrefix + "draft"
    );
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
        console.log(err.response);
        alert("提问箱好像坏掉了，请保存好您的投稿，并通知管理员前来查看！");
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
      dismissBtnStyleClass: "btn-outline-secondary",
      confirmBtnStyleClass: "btn-outline-danger",
      cardBackgroundStyle: "background: rgba(255,255,255,0.9)",
      formStyleClass: "bg-light text-dark",
      h5Style: "color:black",
    };
  },
};
</script>
