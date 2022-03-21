<template>
  <div>
    <Header :hideBackBtn="true"></Header>
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="card shadow-lg my-3" :style="cardBackgroundStyle">
            <div class="card-body">
              <div class="row">
                <div class="col-sm-2 col-md-3 d-none d-sm-block"></div>
                <div class="col-4 col-sm-3 align-self-center">
                  <h5 :style="h5Style">投稿类型：</h5>
                </div>
                <div class="col-8 col-sm-5 col-md-3">
                  <div
                    class="form-check p-1"
                    :class="formStyleClass"
                    v-on:change="onReceiverChange"
                    v-for="q_type in questionTypes"
                    v-bind:key="q_type.name"
                  >
                    <input
                      class="form-check-input"
                      type="radio"
                      :name="q_type.name + '_receiver_radio'"
                      :id="q_type.name + '_receiver_radio'"
                      :value="q_type.name"
                      v-model="type"
                    />
                    <label
                      class="form-check-label"
                      :for="q_type.name + '_receiver_radio'"
                    >
                      {{ q_type.description }}
                    </label>
                  </div>
                </div>
                <div class="col-sm-2 col-md-3 d-none d-sm-block"></div>
              </div>
            </div>
          </div>
          <div class="card shadow-lg my-3" v-bind:style="cardBackgroundStyle">
            <div class="card-body">
              <textarea
                class="col-12 form-control overflow-auto"
                rows="15"
                :class="formStyleClass"
                :maxlength="maxLength"
                :placeholder="textPlaceholder"
                v-model="newQuestionText"
                v-on:keyup="onNewInput"
                v-on:input="onNewInput"
              ></textarea>
              <h5 class="col-12 m-1" :style="h5Style">
                当前字数： {{ currentLength }}/{{ maxLength }}
              </h5>
              <file-pond
                name="mht"
                ref="pond"
                class="filepond"
                itemInsertLocation="after"
                :allowDrop="true"
                :allowBrowse="true"
                :allowMultiple="true"
                v-bind:files="imageFiles"
                v-bind:acceptedFileTypes="acceptedFileTypes"
                v-on:init="onFilepondInitReady"
                v-on:initfile="onFileUpdateStart"
                v-on:updatefiles="onFileUpdated"
                v-if="supportImage"
              />
              <button
                class="btn shadow col-sm-5 col-12"
                :class="[submitBtnActiveClass, submitBtnStyleClass]"
                data-bs-toggle="modal"
                data-bs-target="#submitConfirmModal"
                ref="submitBtn"
              >
                提交
              </button>
            </div>
          </div>
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
            <p>提交后将无法进行更改，建议再读一遍检查一下哦？</p>
            <p>
              确定是投给
              <b>{{
                this.ownerProfiles[this.owner].question_types[this.type]
                  .description
              }}</b>
            </p>
            <p>没有选错投稿类型吧？</p>
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
              data-bs-toggle="modal"
              data-bs-target="#loadingOverlay"
            >
              确认提交
            </button>
          </div>
        </div>
      </div>
    </div>
    <div
      class="modal fade"
      tabindex="-1"
      :data-bs-backdrop="loadingOverlayBackdrop"
      aria-hidden="true"
      id="loadingOverlay"
      ref="loadingOverlay"
    >
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">图片处理中...</h5>
          </div>
          <div class="modal-body">
            <div class="spinner-border" role="status">
              <span class="visually-hidden">Loading...</span>
            </div>
          </div>
          <div class="modal-footer">
            <h5 class="modal-title">如长时间未响应，请刷新页面重试。</h5>
            <button
              type="button"
              class="btn"
              v-show="false"
              data-bs-dismiss="modal"
              ref="loadingOverlayClose"
            >
              close
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
import vueFilePond, { setOptions } from "vue-filepond";
import "filepond/dist/filepond.min.css";
import "filepond-plugin-image-preview/dist/filepond-plugin-image-preview.min.css";
import FilePondPluginFileValidateSize from "filepond-plugin-file-validate-size";
import FilePondPluginFileValidateType from "filepond-plugin-file-validate-type";
import FilePondPluginImagePreview from "filepond-plugin-image-preview";
import zh_cn from "filepond/locale/zh-cn";
import { Modal } from "bootstrap";

setOptions(zh_cn);
setOptions({
  fileValidateTypeLabelExpectedTypes: "请上传图片文件",
  labelIdle: "请把图片拖到这里，或点击此处浏览。请上传至少1张！",
  maxFileSize: "10MB",
  maxFiles: 9,
  server: "/api/image/process",
});
const FilePond = vueFilePond(
  FilePondPluginFileValidateType,
  FilePondPluginFileValidateSize,
  FilePondPluginImagePreview
);
const storagePrefix = "questionNew_";
let currentQuestionTypePrefix = "";
let prevBgClass = "";
export default {
  name: "QuestionNew",
  components: {
    Header,
    FilePond,
  },
  props: {
    owner: String,
  },
  methods: {
    onFilepondInitReady() {
      if (this.supportImage) {
        const input = document.querySelector(".filepond input");
        input.removeAttribute("required");
        input.removeAttribute("capture");
      }
    },
    onFileUpdateStart() {
      this.isProcessingFile = true;
      this.submitBtnActiveClass = "disabled";
    },
    onFileUpdated() {
      this.isProcessingFile = false;
      this.submitBtnActiveClass = "";
    },
    onNewInput() {
      this.currentLength = this.newQuestionText.trim().length;
      localStorage.setItem(
        storagePrefix + currentQuestionTypePrefix + "draft",
        this.newQuestionText
      );
      this.currentLength > 0
        ? (this.submitBtnActiveClass = "")
        : (this.submitBtnActiveClass = "disabled");
      if (this.supportImage)
        !this.isProcessingFile
          ? (this.submitBtnActiveClass = "")
          : (this.submitBtnActiveClass = "disabled");
    },
    profileChanges() {
      this.maxLength =
        this.ownerProfiles[this.owner].question_types[this.type].rune_limit;
      this.supportImage =
        this.ownerProfiles[this.owner].question_types[this.type].support_image;

      // style changes
      // TODO: do not put style changes in code
      // body background
      let newBgClass =
        this.ownerProfiles[this.owner].question_types[this.type].theme
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

      this.supportImage
        ? (this.textPlaceholder = [
            "最高支持上传9张图片，单张大小限制为10MB;",
            "图片展示顺序将保持和上传先后顺序相同;",
            "（可选）请在此输入描述或者署名;",
            "尚未成功提交的文字草稿将被暂存于您的浏览器储存中，但刷新页面后图片需要重新上传，请注意。",
          ].join("\n"))
        : (this.textPlaceholder =
            "尚未成功提交的草稿将被暂存于您的浏览器储存中。");
    },
    onReceiverChange() {
      this.profileChanges();
      currentQuestionTypePrefix = "_" + [this.owner, this.type].join("_") + "_";
      let localVal = localStorage.getItem(
        storagePrefix + currentQuestionTypePrefix + "draft"
      );
      if (localVal && localVal !== "") {
        this.newQuestionText = localVal;
      } else {
        this.newQuestionText = "";
      }
      this.onNewInput();
    },
    async submit() {
      this.loadingOverlayKeyboard = false;
      const authHeader = {
        headers: { Authorization: `Bearer ${this.token}` },
      };
      let images = [];
      if (this.supportImage) {
        let i = 0;
        for (let f of this.$refs.pond.getFiles()) {
          images.push({
            image_id: f.serverId,
            order: i++,
            filename: f.filename,
          });
        }
        if (this.newQuestionText.length === 0) {
          this.newQuestionText = "共" + i + "张，无描述，未署名。";
        }
      }
      try {
        await this.axios.post(
          "/api/questions/submit",
          {
            owner: this.owner,
            type: this.type,
            text: this.newQuestionText,
            images: images,
          },
          authHeader
        );

        localStorage.setItem(
          storagePrefix + currentQuestionTypePrefix + "draft",
          ""
        );
        this.$router.push({
          name: "question",
          query: { token: this.token },
          params: { justSubmitted: true },
        });
      } catch (err) {
        console.log(err);
        if (err.response.status === 400) {
          alert("您的投稿好像不太对劲？ " + err.response.data.error);
        } else if (err.response.status === 409) {
          this.$router.push({
            name: "question",
            query: { token: this.token },
            params: { just_submitted: true },
          });
        } else {
          alert("提问箱好像坏掉了，请保存好您的投稿，并通知管理员前来查看！");
        }
      } finally {
        this.loadingOverlayKeyboard = true;
        const loadingOverlay = Modal.getInstance(
          document.querySelector("#loadingOverlay")
        );
        loadingOverlay.hide();
      }
    },
  },
  beforeMount() {
    // populate question types
    var current = new Date();
    for (var i in this.ownerProfiles[this.owner].question_types) {
      let qt = this.ownerProfiles[this.owner].question_types[i];
      let startTime = Date.parse(qt.start_time);
      let endTime = Date.parse(qt.end_time);
      if (isNaN(startTime) || isNaN(endTime)) this.questionTypes.push(qt);
      else if (startTime <= current && endTime >= current)
        this.questionTypes.push(qt);
    }
    // change body background
    document.body.classList.remove("bg-light");
    this.profileChanges();

    currentQuestionTypePrefix = "_" + [this.owner, this.type].join("_") + "_";
    let localVal = localStorage.getItem(
      storagePrefix + currentQuestionTypePrefix + "draft"
    );
    if (localVal && localVal !== "") {
      this.newQuestionText = localVal;
      this.onNewInput();
    }
    this.$scrollToTop();
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
  mounted() {},
  beforeUnmount() {
    // change back the body background
    document.body.classList.remove("body-background-" + prevBgClass);
    document.body.classList.add("bg-light");
  },
  data() {
    return {
      type: "normal",
      token: "",
      supportImage: false,
      textPlaceHolder: "",
      newQuestionText: "",
      questionTypes: [],
      currentLength: 0,
      maxLength: 500,
      submitBtnActiveClass: "disabled",
      submitBtnStyleClass: "btn-outline-success",
      dismissBtnStyleClass: "btn-outline-secondary",
      confirmBtnStyleClass: "btn-outline-danger",
      cardBackgroundStyle: "background: rgba(255,255,255,0.9)",
      formStyleClass: "bg-light text-dark",
      h5Style: "color:black",
      imageFiles: [],
      acceptedFileTypes: ["image/*"],
      loadingOverlayBackdrop: "static",
      isProcessingFile: false,
    };
  },
};
</script>
