<template>
  <div>
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="card shadow-lg my-3">
            <div class="card-body py-3 border-bottom text-start text-sm-center">
              <div class="fw-semibold">投稿时间：{{ asked_at }}</div>
              <div class="small text-muted mt-1" v-if="ip">
                IP：{{ ip }}
                <span v-if="ip_addr || ip_isp"
                  >（{{ [ip_addr, ip_isp].filter(Boolean).join(" / ") }}）</span
                >
              </div>
              <div class="small text-muted mt-1" v-if="moderated_at">
                审核时间：{{ formatTime(moderated_at) }}
              </div>
            </div>
            <div class="card-body overflow-auto">
              <div class="container">
                <div class="row">
                  <div class="col-12" v-if="images?.length > 0">
                    <image-display
                      :images="images"
                      slideHeight="300px"
                      :withNavigation="false"
                    />
                  </div>
                  <div
                    class="col-12 mt-3 d-flex justify-content-end"
                    v-if="images?.length > 0"
                  >
                    <button
                      class="btn btn-outline-info btn-sm"
                      v-on:click="toFullscreen()"
                    >
                      图片全屏
                    </button>
                  </div>
                  <div class="col-12 mt-2">
                    <div
                      class="alert alert-warning text-start"
                      v-if="isBlockedModeration"
                    >
                      <div class="fw-semibold mb-2">审核依据</div>
                      <p class="mb-1">{{ moderationDetailText }}</p>
                    </div>
                    <div
                      class="border rounded p-3 text-start bg-light"
                      v-if="isBlockedModeration && !rawContentRevealed"
                    >
                      <p class="mb-2 text-muted">
                        原文可能包含隐私、安全或骚扰内容，默认隐藏。
                      </p>
                      <button
                        class="btn btn-sm btn-outline-danger"
                        v-if="!rawRevealWarningOpen"
                        v-on:click="rawRevealWarningOpen = true"
                      >
                        查看原文
                      </button>
                      <div v-else>
                        <p class="mb-2 text-danger">
                          确认后将显示未经处理的投稿原文。
                        </p>
                        <button
                          class="btn btn-sm btn-danger me-2"
                          v-on:click="rawContentRevealed = true"
                        >
                          确认显示原文
                        </button>
                        <button
                          class="btn btn-sm btn-secondary"
                          v-on:click="rawRevealWarningOpen = false"
                        >
                          取消
                        </button>
                      </div>
                    </div>
                    <div v-if="shouldShowQuestionText" style="line-break: anywhere">
                      <p
                        v-for="(sentence, i) in formatText(question_text)"
                        v-bind:key="i"
                        class="lh-lg text-start"
                      >
                        {{ sentence }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-12">
          <div class="card shadow-lg my-3">
            <div class="card-body py-3 border-bottom text-start text-sm-center">
              <div class="fw-semibold">
                回复时间：{{ answered_at !== "" ? answered_at : "尚未回复" }}
              </div>
              <div class="small text-muted mt-1" v-if="visit_count > 0">
                最近查看时间：{{ last_visited_at }}，总查看次数：{{ visit_count }}
              </div>
            </div>
            <div class="card-body overflow-auto" style="height: 150px">
              <div style="line-break: anywhere">
                <p
                  v-for="(sentence, i) in formatText(previous_answer_text)"
                  v-bind:key="i"
                  class="lh-lg text-start"
                >
                  {{ sentence }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="row">
        <div class="card shadow-lg my-3 border">
          <div class="card-body">
            <textarea
              class="col-12"
              rows="8"
              v-model="answer_text"
              v-on:keyup="onNewInput"
              v-on:input="onNewInput"
            ></textarea>
            <button
              class="btn shadow btn-outline-success col-12 col-sm-3"
              v-on:click="submit"
            >
              提交或更新
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
import ImageDisplay from "./ImageDisplay.vue";
const storagePrefix = "AnswerView_draft_";
export default {
  name: "AnswerView",
  components: { Header, ImageDisplay },
  props: { changeQuestion: String },
  emits: ["fullscreenImg"],
  watch: {
    changeQuestion: function (uuid) {
      if (!uuid) {
        this.resetDetailState();
        return;
      }
      this.uuid = uuid;
      this.getQuestionAndAnswer(uuid);
    },
  },
  methods: {
    toFullscreen() {
      this.$emit("fullscreenImg", this.images);
    },
    onNewInput() {
      localStorage.setItem(storagePrefix + this.uuid, this.answer_text);
    },
    formatTime(timeStr) {
      let time = Date.parse(timeStr);
      if (time === 0) {
        return "";
      }
      return new Date(timeStr).toLocaleString("zh-CN", { hourCycle: "h23" });
    },
    resetDetailState() {
      this.answer_text = "";
      this.question_text = "";
      this.asked_at = "";
      this.previous_answer_text = "";
      this.answered_at = "";
      this.last_visited_at = "";
      this.visit_count = 0;
      this.images = [];
      this.ip = "";
      this.ip_addr = "";
      this.ip_isp = "";
      this.rawContentRevealed = false;
      this.rawRevealWarningOpen = false;
      this.moderation_status = "";
      this.moderation_source = "";
      this.moderation_category = "";
      this.moderation_reason = "";
      this.moderation_short_reason = "";
      this.moderation_rationale = "";
      this.moderated_at = "";
    },
    getQuestionAndAnswer(uuid) {
      const requestedUuid = uuid;
      this.resetDetailState();
      this.detailLoading = true;
      const authHeader = {
        headers: { Authorization: `Bearer ${this.$route.query.token}` },
      };
      this.axios
        .get("/api/owner/questions/" + uuid, authHeader)
        .then((resp) => {
          if (this.uuid !== requestedUuid) return;
          this.question_text = resp.data.text;
          this.asked_at = this.formatTime(resp.data.asked_at);
          this.previous_answer_text = resp.data.answer;
          this.answer_text = resp.data.answer;
          this.answered_at = this.formatTime(resp.data.answered_at);
          this.last_visited_at = this.formatTime(resp.data.last_visited_at);
          this.visit_count = resp.data.visit_count;
          this.images = resp.data.images;
          this.ip = resp.data.ip || "";
          this.ip_addr = resp.data.ip_addr || "";
          this.ip_isp = resp.data.ip_isp || "";
          const moderation = resp.data.moderation || {};
          this.moderation_status = moderation.status || "";
          this.moderation_source = moderation.source || "";
          this.moderation_category = moderation.category || "";
          this.moderation_reason = moderation.reason || "";
          this.moderation_short_reason = moderation.short_reason || "";
          this.moderation_rationale = moderation.rationale || "";
          this.moderated_at = moderation.updated_at || "";
          if (this.answer_text.length === 0) {
            let localVal = localStorage.getItem(storagePrefix + this.uuid);
            if (localVal && localVal !== "") {
              this.answer_text = localVal;
            }
          }
        })
        .catch((err) => {
          if (this.uuid === requestedUuid) console.log(err);
        })
        .finally(() => {
          if (this.uuid === requestedUuid) this.detailLoading = false;
        });
    },
    submit() {
      const authHeader = {
        headers: { Authorization: `Bearer ${this.$route.query.token}` },
      };
      this.axios
        .put(
          "/api/owner/questions/" + this.uuid + "/answer",
          {
            uuid: this.uuid,
            answer: this.answer_text,
            answered_by: "manual",
          },
          authHeader
        )
        .then(() => {
          localStorage.removeItem(storagePrefix + this.uuid);
          this.getQuestionAndAnswer(this.uuid);
        })
        .catch((err) => {
          console.log(err.response);
        });
    },
    isChineseText(text) {
      return /[\u3400-\u9fff]/.test(text || "");
    },
  },
  computed: {
    isBlockedModeration() {
      return this.moderation_status === "blocked";
    },
    shouldShowQuestionText() {
      if (this.detailLoading) return false;
      return !this.isBlockedModeration || this.rawContentRevealed;
    },
    moderationDetailText() {
      if (this.isChineseText(this.moderation_rationale)) return this.moderation_rationale;
      if (this.isChineseText(this.moderation_short_reason)) return this.moderation_short_reason;
      return this.moderationChineseFallback;
    },
    moderationChineseFallback() {
      const categoryLabels = {
        privacy: "模型判断该投稿可能涉及隐私风险，需要进入审核队列。",
        doxxing: "模型判断该投稿可能涉及人肉或隐私泄露，需要进入审核队列。",
        identity_speculation: "模型判断该投稿可能涉及身份猜测，需要进入审核队列。",
        harassment: "模型判断该投稿可能包含骚扰或攻击内容，需要进入审核队列。",
        threats: "模型判断该投稿可能包含威胁内容，需要进入审核队列。",
        spam: "模型判断该投稿可能是垃圾内容，需要进入审核队列。",
        explicit_sexual_content: "模型判断该投稿可能包含露骨内容，需要进入审核队列。",
        fan_drama: "模型判断该投稿可能引导粉圈争议，需要进入审核队列。",
        other: "模型判断该投稿需要人工复核。",
        safe: "未发现明显风险。",
      };
      const reasonLabels = {
        model_reject: "模型判断该投稿需要人工复核。",
        policy_block: "该投稿触发审核策略，需要进入审核队列。",
        manual: "该投稿由人工标记进入审核队列。",
      };
      return (
        categoryLabels[this.moderation_category] ||
        reasonLabels[this.moderation_reason] ||
        "审核信息暂缺"
      );
    },
    formatText() {
      return (text) => {
        if (text !== null) {
          return text.split(/(?:\r\n|\r|\n)/g);
        }
        return [];
      };
    },
  },
  data() {
    return {
      asked_at: "",
      question_text: "",
      answered_at: "",
      previous_answer_text: "",
      answer_text: "",
      last_visited_at: "",
      visit_count: 0,
      uuid: "",
      images: [],
      ip: "",
      ip_addr: "",
      ip_isp: "",
      moderation_status: "",
      moderation_source: "",
      moderation_category: "",
      moderation_reason: "",
      moderation_short_reason: "",
      moderation_rationale: "",
      moderated_at: "",
      rawContentRevealed: false,
      rawRevealWarningOpen: false,
      detailLoading: false,
    };
  },
};
</script>
