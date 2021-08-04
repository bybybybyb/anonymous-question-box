<template>
  <div>
    <Header :hideBackBtn="true"></Header>
    <div v-if="just_submitted">
      <QuestionSubmission :token="token" />
      <QuestionDisplay :token="token" />
    </div>
    <div v-else>
      <QuestionDisplay :token="token" />
      <QuestionSubmission :token="token" />
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
import QuestionDisplay from "./QuestionDisplay.vue";
import QuestionSubmission from "./QuestionSubmission.vue";
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
    console.log(this.just_submitted);
    this.token = this.$route.query.token;
  },
  data() {
    return {
      token: "",
    };
  },
};
</script>