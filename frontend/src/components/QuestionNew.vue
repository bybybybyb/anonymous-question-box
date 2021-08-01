<template>
  <div>
    <Header :hideBackBtn="true"></Header>
    <div class="container">
      <div class="card my-3">
        <div class="card-body">
          <div class="row">
            <div class="col-4">
              <h5>收件人：</h5>
            </div>
            <div class="col-8">
              <select
                class="form-select form-select-sm"
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
      <div class="card my-3">
        <div class="card-body">
          <textarea
            class="col-12"
            rows="20"
            v-model="new_question_text"
            :maxlength="maxLength"
            v-on:keyup="onNewInput"
          ></textarea>
          <h4 class="col-12">当前字数： {{ currentLength }}/{{ maxLength }}</h4>
          <button
            v-bind:class="[submitBtnStyleClasses, submitBtnActiveClass]"
            v-on:click="submit"
          >
            提交
          </button>
          <h5 class="col-12 m-2">
            小提示：尚未成功提交的草稿将被暂存于您的浏览器储存中。
          </h5>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
export default {
  name: "QuestionNew",
  components: {
    Header,
  },
  methods: {
    onNewInput() {
      this.currentLength = this.new_question_text.length;
      localStorage.draft = this.new_question_text;
      this.new_question_text.length > 0
        ? (this.submitBtnActiveClass = "")
        : (this.submitBtnActiveClass = "disabled");
    },
    onReceiverChange(event) {
      this.maxLength =
        this.ownerProfiles[this.owner].question_types[
          event.target.value
        ].rune_limit;
    },
    submit() {
      const authHeader = {
        headers: { Authorization: `Bearer ${this.$route.query.token}` },
      };
      console.log(this.new_question_text);
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
        .then((resp) => {
          console.log(resp);
          localStorage.draft = "";
          this.$router.push({
            name: "submission",
            query: { token: this.$route.query.token },
          });
        })
        .catch((err) => {
          alert(err.response);
        });
    },
  },
  mounted() {
    if (localStorage.draft != null) {
      this.new_question_text = localStorage.draft;
      this.onNewInput();
    }
  },
  data() {
    return {
      type: "normal",
      // TODO: check owner existence before assignment
      owner: this.$route.query.owner,
      question_text: "",
      asked_at: "",
      answer_text: "",
      answered_at: "",
      new_question_text: "",
      currentLength: 0,
      maxLength: 500,
      submitBtnStyleClasses: "btn btn-outline-success col-sm-5 col-12",
      submitBtnActiveClass: "disabled",
    };
  },
};
</script>
