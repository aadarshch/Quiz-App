(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("quiz-data").textContent);
  var quizCard = document.getElementById("quiz-card");
  var endCard = document.getElementById("end-card");
  var promptEl = document.getElementById("question-prompt");
  var optionsEl = document.getElementById("options");
  var questionIndexEl = document.getElementById("question-index");
  var progressLabel = document.getElementById("progress-label");
  var progressFill = document.getElementById("progress-fill");
  var feedbackEl = document.getElementById("feedback");
  var nextBtn = document.getElementById("next-btn");
  var scoreValue = document.getElementById("score-value");
  var scoreTotal = document.getElementById("score-total");
  var scoreMessage = document.getElementById("score-message");
  var reviewEl = document.getElementById("review");
  var retryBtn = document.getElementById("retry-btn");

  var soundUrls = {
    wrong: "/static/sounds/wrong.mp3",
    end: "/static/sounds/2wrong.mp3"
  };
  var soundVolumes = { wrong: 0.6, end: 0.7 };
  var fallbackPlayers = {};
  Object.keys(soundUrls).forEach(function (name) {
    var player = new Audio(soundUrls[name]);
    player.preload = "auto";
    player.volume = soundVolumes[name];
    fallbackPlayers[name] = player;
  });

  var audioCtx = null;
  var soundBuffers = {};
  var AudioCtor = window.AudioContext || window.webkitAudioContext;

  function initAudio() {
    if (!AudioCtor) {
      return;
    }
    audioCtx = new AudioCtor();
    Object.keys(soundUrls).forEach(function (name) {
      fetch(soundUrls[name])
        .then(function (response) {
          return response.arrayBuffer();
        })
        .then(function (data) {
          return new Promise(function (resolve, reject) {
            audioCtx.decodeAudioData(data, resolve, reject);
          });
        })
        .then(function (buffer) {
          soundBuffers[name] = buffer;
        })
        .catch(function () {});
    });
  }

  var queue = [];
  var index = 0;
  var score = 0;
  var missed = [];
  var answered = false;

  function playSound(name) {
    if (audioCtx && soundBuffers[name]) {
      if (audioCtx.state === "suspended") {
        audioCtx.resume().catch(function () {});
      }
      var source = audioCtx.createBufferSource();
      var gain = audioCtx.createGain();
      gain.gain.value = soundVolumes[name];
      source.buffer = soundBuffers[name];
      source.connect(gain);
      gain.connect(audioCtx.destination);
      source.start(0);
      return;
    }
    var player = fallbackPlayers[name];
    player.currentTime = 0;
    var promise = player.play();
    if (promise && promise.catch) {
      promise.catch(function () {});
    }
  }

  function renderPrompt(prompt) {
    promptEl.textContent = "";
    var parts = prompt.split("_____");
    parts.forEach(function (part, i) {
      promptEl.appendChild(document.createTextNode(part));
      if (i < parts.length - 1) {
        var blank = document.createElement("span");
        blank.className = "blank";
        blank.textContent = "_____";
        promptEl.appendChild(blank);
      }
    });
  }

  function render() {
    answered = false;
    var question = queue[index];
    var total = queue.length;

    questionIndexEl.textContent = "Question " + (index + 1);
    progressLabel.textContent = "Question " + (index + 1) + " of " + total;
    progressFill.style.width = (index / total) * 100 + "%";

    renderPrompt(question.prompt);

    optionsEl.textContent = "";
    var letters = ["A", "B", "C", "D"];
    question.options.forEach(function (option, i) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "option";

      var key = document.createElement("span");
      key.className = "option-key";
      key.textContent = letters[i] || String(i + 1);

      var label = document.createElement("span");
      label.className = "option-text";
      label.textContent = option;

      button.appendChild(key);
      button.appendChild(label);
      button.addEventListener("click", function () {
        choose(i, button);
      });
      optionsEl.appendChild(button);
    });

    feedbackEl.textContent = "";
    feedbackEl.className = "feedback";
    nextBtn.hidden = true;
    nextBtn.textContent = index === total - 1 ? "See results" : "Next question";
  }

  function choose(chosen, chosenButton) {
    if (answered) {
      return;
    }
    answered = true;
    var question = queue[index];
    var correct = chosen === question.answerIndex;
    var total = queue.length;

    if (!correct) {
      playSound("wrong");
    }

    Array.prototype.forEach.call(optionsEl.children, function (button, i) {
      button.disabled = true;
      if (i === question.answerIndex) {
        button.classList.add("correct");
      } else if (i === chosen) {
        button.classList.add("wrong");
      }
    });

    progressFill.style.width = ((index + 1) / total) * 100 + "%";

    if (correct) {
      score += 1;
      feedbackEl.textContent = "Correct.";
      feedbackEl.className = "feedback good";
    } else {
      missed.push(question);
      feedbackEl.textContent = "Not quite — the answer is: " + question.options[question.answerIndex];
      feedbackEl.className = "feedback bad";
    }

    nextBtn.hidden = false;
  }

  function finish() {
    quizCard.hidden = true;
    endCard.hidden = false;

    var total = queue.length;
    var percent = total > 0 ? Math.round((score / total) * 100) : 0;

    if (missed.length > 5) {
      playSound("end");
    }

    scoreValue.textContent = String(score);
    scoreTotal.textContent = "/" + total;

    if (percent === 100) {
      scoreMessage.textContent = "Flawless — every answer correct.";
    } else if (percent >= 80) {
      scoreMessage.textContent = "Sharp work. A couple of misses to review.";
    } else if (percent >= 50) {
      scoreMessage.textContent = "Solid start — review the misses below.";
    } else {
      scoreMessage.textContent = "Keep going — the correct answers are below.";
    }

    reviewEl.textContent = "";
    missed.forEach(function (question) {
      var item = document.createElement("div");
      item.className = "review-item";

      var prompt = document.createElement("p");
      prompt.className = "review-prompt";
      prompt.textContent = question.prompt;

      var answer = document.createElement("p");
      answer.className = "review-answer";
      answer.textContent = "Answer: " + question.options[question.answerIndex];

      item.appendChild(prompt);
      item.appendChild(answer);
      reviewEl.appendChild(item);
    });

    retryBtn.hidden = missed.length === 0;

    fetch("/api/quiz/" + data.id + "/attempt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ score: score, total: total })
    }).catch(function () {});
  }

  nextBtn.addEventListener("click", function () {
    index += 1;
    if (index >= queue.length) {
      finish();
    } else {
      render();
    }
  });

  retryBtn.addEventListener("click", function () {
    queue = missed.slice();
    index = 0;
    score = 0;
    missed = [];
    endCard.hidden = true;
    quizCard.hidden = false;
    render();
  });

  initAudio();
  queue = data.questions.slice();
  render();
})();
