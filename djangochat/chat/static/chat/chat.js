(function () {
  function escapeHtml(text) {
    return $("<div>").text(text || "").html();
  }

  function roleLabel(role) {
    if (role === "MOD") return "Modérateur";
    if (role === "MEMBER") return "Membre";
    if (role === "OWNER") return "Créateur";
    return role || "";
  }

  function relativeTimeFromNow(iso) {
    if (!iso) return "";
    const now = Date.now();
    const then = Date.parse(iso);
    if (Number.isNaN(then)) return "";
    const diffSec = Math.max(0, Math.floor((now - then) / 1000));
    if (diffSec < 60) return diffSec + " s";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + " min";
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return diffHour + " h";
    const diffDay = Math.floor(diffHour / 24);
    return diffDay + " j";
  }

  function renderMessage(m) {
    const isSystem = m.content && m.content.indexOf("[SYSTEM] ") === 0;
    const displayContent = isSystem ? m.content.slice(9) : m.content;
    const safeAuthor = escapeHtml(m.author);
    const safeContent = escapeHtml(displayContent);

    let delBtn = "";
    if (!isSystem && m.can_delete && !m.is_deleted) {
      delBtn =
        '<button class="btn btn-sm btn-link text-danger p-0 ms-2 delete-btn" data-id="' +
        m.id +
        '" aria-label="Supprimer">' +
        '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M3 6h18"/>' +
        '<path d="M8 6V4h8v2"/>' +
        '<path d="M6 6l1 14h10l1-14"/>' +
        '<path d="M10 11v6"/>' +
        '<path d="M14 11v6"/>' +
        "</svg></button>";
    }

    const isOwn = window.CHAT_CONFIG && window.CHAT_CONFIG.currentUser === m.author;
    const rowClass = isSystem ? "message-system" : isOwn ? "message-own" : "message-other";
    return (
      '\n      <div class="mb-2 ' +
      rowClass +
      '" data-id="' +
      m.id +
      '">\n        ' +
      (isSystem ? "" : "<strong>" + safeAuthor + " : </strong>") +
      '\n        <div class="message-text">' +
      safeContent +
      "</div>\n        " +
      (isSystem
        ? ""
        : '<div class="message-meta text-muted">\n          <span>' +
          new Date(m.created_at).toLocaleString() +
          "</span>\n          " +
          delBtn +
          "\n        </div>") +
      "\n      </div>\n    "
    );
  }

  function initChatRoom() {
    if (!window.CHAT_CONFIG || !window.CHAT_CONFIG.apiMessagesUrl) return;
    if (!$("#chat-box").length) return;

    let lastSync = null;

    function getLastId() {
      const items = $("#chat-box [data-id]");
      if (!items.length) return 0;
      return parseInt($(items[items.length - 1]).attr("data-id"), 10) || 0;
    }

    function scrollToBottomIfNearBottom() {
      const box = $("#chat-box")[0];
      const distanceFromBottom = box.scrollHeight - box.scrollTop - box.clientHeight;
      if (distanceFromBottom < 120) {
        box.scrollTop = box.scrollHeight;
      }
    }

    function fetchMessages() {
      const after = getLastId();
      $.get(window.CHAT_CONFIG.apiMessagesUrl, { after: after, since: lastSync })
        .done(function (resp) {
          if (resp.messages && resp.messages.length) {
            resp.messages.forEach(function (m) {
              $("#chat-box").append(renderMessage(m));
            });
            scrollToBottomIfNearBottom();
          }

          if (resp.deleted_ids && resp.deleted_ids.length) {
            resp.deleted_ids.forEach(function (id) {
              const el = $('#chat-box [data-id="' + id + '"]');
              if (!el.length) return;
            el.find(".message-text").text("[message supprimé]");
              el.find(".delete-btn").remove();
            });
          }

          lastSync = resp.server_now || new Date().toISOString();
        })
      .fail(function (xhr) {
        if (xhr && xhr.status === 403) {
          window.location.href = window.CHAT_CONFIG.roomDetailUrl;
          return;
        }
        // silencieux
      });
    }

    function sendMessage() {
      const content = ($("#msg-input").val() || "").trim();
      if (!content) return;

      $.post(window.CHAT_CONFIG.apiSendUrl, {
        content: content,
        csrfmiddlewaretoken: window.CHAT_CONFIG.csrfToken,
      })
        .done(function (resp) {
          if (resp.ok && resp.message) {
            $("#chat-box").append(renderMessage(resp.message));
            $("#msg-input").val("");
            const box = $("#chat-box")[0];
            box.scrollTop = box.scrollHeight;
          }
        })
        .fail(function (xhr) {
          alert("Erreur envoi message (" + xhr.status + ")");
        });
    }

    function deleteMessage(messageId) {
      const url = window.CHAT_CONFIG.apiDeleteBase + messageId + "/";
      $.post(url, { csrfmiddlewaretoken: window.CHAT_CONFIG.csrfToken })
        .done(function () {
          // update UI: remplace contenu
          const el = $('#chat-box [data-id="' + messageId + '"]');
          el.find(".message-text").text("[message supprimé]");
          el.find(".delete-btn").remove();
        })
        .fail(function (xhr) {
          alert("Impossible de supprimer (" + xhr.status + ")");
        });
    }

    fetchMessages();
    setInterval(fetchMessages, 1500);

    $("#send-btn").on("click", sendMessage);
    $("#msg-input").on("keypress", function (e) {
      if (e.which === 13) sendMessage();
    });
    const typingIndicator = $("#typing-indicator");
    let lastTypingSent = 0;

    function sendTypingPing() {
      if (!window.CHAT_CONFIG.apiTypingUrl) return;
      $.post(window.CHAT_CONFIG.apiTypingUrl, {
        csrfmiddlewaretoken: window.CHAT_CONFIG.csrfToken,
      });
    }

    function pollTyping() {
      if (!window.CHAT_CONFIG.apiTypingUrl || !typingIndicator.length) return;
      $.get(window.CHAT_CONFIG.apiTypingUrl)
        .done(function (resp) {
          if (resp.typing && resp.typing.length) {
            const verb = resp.typing.length > 1 ? "sont" : "est";
            typingIndicator.text(resp.typing.join(", ") + " " + verb + " en train d'écrire...");
            typingIndicator.addClass("typing-active");
          } else {
            typingIndicator.text("");
            typingIndicator.removeClass("typing-active");
          }
        })
        .fail(function () {
          typingIndicator.text("");
          typingIndicator.removeClass("typing-active");
        });
    }

    $("#msg-input").on("input", function () {
      const now = Date.now();
      if (now - lastTypingSent < 800) return;
      lastTypingSent = now;
      sendTypingPing();
    });

    if (window.CHAT_CONFIG.apiTypingUrl && typingIndicator.length) {
      pollTyping();
      setInterval(pollTyping, 1000);
    }
    $(".emoji-btn").on("click", function () {
      const emo = $(this).data("emoji");
      const input = $("#msg-input");
      input.val((input.val() || "") + emo);
      input.focus();
    });

    $("#chat-box").on("click", ".delete-btn", function () {
      const id = parseInt($(this).data("id"), 10);
      if (!id) return;
      deleteMessage(id);
    });

    const box = $("#chat-box")[0];
    if (box) box.scrollTop = box.scrollHeight;
  }

  function initRoomList() {
    if (!window.CHAT_LIST_CONFIG || !window.CHAT_LIST_CONFIG.apiRoomListUrl) return;
    const listEl = $("#room-list");
    if (!listEl.length) return;

    const lockSvg =
      '<span class="room-lock" aria-label="Salon protege">' +
      '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<rect x="3" y="11" width="18" height="10" rx="2"/>' +
      '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>' +
      "</svg>" +
      "</span>";

    function renderRoomItem(r) {
      let lastHtml = '<small class="text-muted">Aucun message</small>';
      if (r.last_message_content) {
        if (r.last_message_is_deleted) {
          lastHtml = '<small class="text-muted">[message supprimé]</small>';
        } else {
          const author = escapeHtml(r.last_message_author || "");
          const content = escapeHtml(r.last_message_content || "");
          const rel = relativeTimeFromNow(r.last_message_created_at);
          const relText = rel ? " - il y a " + rel : "";
          lastHtml =
            '<small class="text-muted">' +
            author +
            ": " +
            content +
            relText +
            "</small>";
        }
      }

      const roomUrl = window.CHAT_LIST_CONFIG.roomDetailBase + r.id + "/";
      return (
        '<a class="list-group-item list-group-item-action d-flex justify-content-between align-items-center" href="' +
        roomUrl +
        '">' +
        '<div>' +
        '<div class="d-flex align-items-center gap-2">' +
        "<div>" +
        escapeHtml(r.name) +
        "</div>" +
        (r.has_password ? lockSvg : "") +
        "</div>" +
        lastHtml +
        "</div>" +
        '<small class="text-muted">Créé par ' +
        escapeHtml(r.created_by || "") +
        "</small>" +
        "</a>"
      );
    }

    function fetchRooms() {
      $.get(window.CHAT_LIST_CONFIG.apiRoomListUrl)
        .done(function (resp) {
          if (!resp.rooms) return;
          const html = resp.rooms.map(renderRoomItem).join("");
          listEl.html(html || '<div class="list-group-item">Aucun salon pour l\'instant.</div>');
        })
        .fail(function () {
          // silencieux
        });
    }

    fetchRooms();
    setInterval(fetchRooms, 3000);
  }

  function initRoomState() {
    if (!window.CHAT_CONFIG || !window.CHAT_CONFIG.apiRoomStateUrl) return;
    const membersEl = $("#members-list");
    if (!membersEl.length) return;

    function renderMembers(resp) {
      if (resp.room && resp.room.name) {
        $("#room-name").text(resp.room.name);
        $(".rename-input").val(resp.room.name);
      }
      if (resp.role) {
        $("#current-role").text(roleLabel(resp.role));
      }
      if (!resp.members) return;

      const groups = { OWNER: [], MOD: [], MEMBER: [], BANNED: [] };
      resp.members.forEach(function (m) {
        if (!groups[m.role]) groups[m.role] = [];
        groups[m.role].push(m);
      });

      const order = ["OWNER", "MOD", "MEMBER", "BANNED"];
      const currentRole = resp.role;
      const currentUserId = window.CHAT_CONFIG.currentUserId;
      const csrf = escapeHtml(window.CHAT_CONFIG.csrfToken || "");

      let html = "";
      order.forEach(function (role) {
        const list = groups[role] || [];
        if (!list.length) return;

        const title =
          role === "OWNER"
            ? "Créateur"
            : role === "MOD"
            ? "Modérateur"
            : role === "MEMBER"
            ? "Membres"
            : role === "BANNED"
            ? "Bannis"
            : role;

        html += '<div class="member-role-block">';
        html += '<div class="member-role-title">' + title + "</div>";
        html += '<div class="list-group">';

        list.forEach(function (mem) {
          const mutedClass = mem.role === "BANNED" ? "opacity-50" : "";
          let actions = "";

          if (
            currentRole === "OWNER" &&
            mem.role !== "OWNER" &&
            mem.user_id !== currentUserId
          ) {
            if (mem.role === "MOD") {
              actions +=
                '<form method="post" action="' +
                window.CHAT_CONFIG.apiUnmodBase +
                mem.user_id +
                '/" class="d-inline">' +
                '<input type="hidden" name="csrfmiddlewaretoken" value="' +
                csrf +
                '">' +
                '<button type="submit" class="btn btn-sm btn-outline-secondary member-action-btn">Retirer modérateur</button>' +
                "</form>";
            } else if (mem.role !== "BANNED") {
              actions +=
                '<form method="post" action="' +
                window.CHAT_CONFIG.apiModBase +
                mem.user_id +
                '/" class="d-inline">' +
                '<input type="hidden" name="csrfmiddlewaretoken" value="' +
                csrf +
                '">' +
                '<button type="submit" class="btn btn-sm btn-outline-primary member-action-btn">Mettre modérateur</button>' +
                "</form>";
            }
          }

          if (currentRole === "OWNER" || currentRole === "MOD") {
            if (mem.role === "BANNED") {
              actions +=
                '<form method="post" action="' +
                window.CHAT_CONFIG.apiUnbanBase +
                mem.user_id +
                '/" class="d-inline">' +
                '<input type="hidden" name="csrfmiddlewaretoken" value="' +
                csrf +
                '">' +
                '<button type="submit" class="btn btn-sm btn-outline-success member-action-btn">Débannir</button>' +
                "</form>";
            } else if (mem.role !== "OWNER" && mem.user_id !== currentUserId) {
              actions +=
                '<form method="post" action="' +
                window.CHAT_CONFIG.apiBanBase +
                mem.user_id +
                '/" class="d-inline">' +
                '<input type="hidden" name="csrfmiddlewaretoken" value="' +
                csrf +
                '">' +
                '<button type="submit" class="btn btn-sm btn-outline-danger member-action-btn">Bannir</button>' +
                "</form>";
            }
          }

          html +=
            '<div class="list-group-item member-row d-flex flex-column ' +
            mutedClass +
            '">' +
            '<div class="member-name"><strong>' +
            escapeHtml(mem.username) +
            "</strong></div>" +
            '<div class="member-actions">' +
            actions +
            "</div>" +
            "</div>";
        });

        html += "</div></div>";
      });

      membersEl.html(html);
    }

    function fetchState() {
      $.get(window.CHAT_CONFIG.apiRoomStateUrl)
        .done(function (resp) {
          renderMembers(resp);
        })
        .fail(function (xhr) {
          if (xhr && xhr.status === 403) {
            window.location.href = window.CHAT_CONFIG.roomDetailUrl;
            return;
          }
          // silencieux
        });
    }

    fetchState();
    setInterval(fetchState, 3000);
  }

  $(function () {
    initChatRoom();
    initRoomList();
    initRoomState();
  });
})();
