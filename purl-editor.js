var editor = CodeMirror.fromTextArea(document.getElementById("code"), {
  mode: "text/x-yaml",
  theme: "default",
  lineNumbers: true,
  matchBrackets: true,
  showCursorWhenSelecting: true,
  extraKeys: {
    "F11": function(cm) {
      if (!cm.getOption("fullScreen")) {
        bootbox.alert({
          title: 'Entering fullscreen editor mode',
          message: 'To leave fullscreen mode, press F11 or Esc',
          closeButton: false,
        });
      }
      cm.setOption("fullScreen", !cm.getOption("fullScreen"));
    },
    "Esc": function(cm) {
      if (cm.getOption("fullScreen"))
        cm.setOption("fullScreen", false);
    },
    Tab: function(cm) {
      var spaces = Array(cm.getOption("indentUnit") + 1).join(" ");
      cm.replaceSelection(spaces);
    },
    "Ctrl-S": validate,
    "Ctrl-Space": "autocomplete"
  }
});


// Add anyword hinting to the editor:
CodeMirror.commands.autocomplete = function(cm) {
  cm.showHint({hint: CodeMirror.hint.anyword});
}


// Disable the save button when the contents of the editor are changed:
editor.on("change", function() {
  document.getElementById("save-btn").disabled = true;
});


// Disable the editor if the user refreshes or otherwise leaves the page:
window.onbeforeunload = function() {
  document.getElementById("save-btn").disabled = true;
}


var validate = function() {
  // Save the contents of the editor to its associated text area:
  editor.save();

  // Extract the code from the text area:
  var code = document.getElementById("code").value;

  // Clear the status area:
  var statusArea = document.getElementById("status-area");
  statusArea.style.color = "#000000";
  statusArea.innerHTML = "Validating ...";

  // Embed the code into a POST request and send it to the server for processing:
  var request = new XMLHttpRequest();
  request.onreadystatechange = function() {
    if (request.readyState === 4) {
      if (request.status === 200) {
        statusArea.style.color = "#00CD00";
        statusArea.innerHTML = "Validation successful";
        // Enable the save button:
        document.getElementById("save-btn").disabled = false;
      }
      else {
        // Display the error message in the status area. Note that we must replace any angle
        // angle brackets with HTML escape codes.
        alertText = "Validation failed.\n\n" +
          request.responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        alertText = '<div class="preformatted">' + alertText + '</div>';
        statusArea.style.color = "#FF0000";
        statusArea.innerHTML = alertText;
        document.getElementById("save-btn").disabled = true;
      }
    }
  }
  request.open('POST', 'http://127.0.0.1:5000/validate', true);
  request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  request.send("code=" + encodeURIComponent(code));
};


var save = function() {
  // Get a confirmation from the user:
  bootbox.confirm({ 
    size: "large",
    closeButton: false,
    title: "Confirm save",
    message: 'By saving now <b>you will initiate a pull request</b> in the purl.obolibrary.org ' +
      'repository containing the changes you have made to this file. Please confirm that you ' +
      'really want to do this.',
    buttons: {
      confirm: {
        label: 'Save',
        className: 'btn-danger'
      },
      cancel: {
        label: 'Cancel',
        className: 'btn-primary'
      }
    },
    callback: function(result) {
      if (result) {
        // Disable the save button:
        document.getElementById("save-btn").disabled = true;

        // Extract the code from the text area:
        var code = document.getElementById("code").value;

        // Clear the status area:
        var statusArea = document.getElementById("status-area");
        statusArea.style.color = "#000000";
        statusArea.innerHTML = "Saving ...";

        // Embed the code into a POST request and send it to the server for processing:
        var request = new XMLHttpRequest();
        request.onreadystatechange = function() {
          if (request.readyState === 4) {
            if (request.status === 200) {
              statusArea.style.color = "#00CD00";
              statusArea.innerHTML = "Save successful";
            }
            else {
              // Display the error message in the status area. Note that we must replace any angle
              // angle brackets with HTML escape codes.
              alertText = "Save failed.\n\n" +
                request.responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
              alertText = '<div class="preformatted">' + alertText + '</div>';
              statusArea.style.color = "#FF0000";
              statusArea.innerHTML = alertText;
            }
          }
        }
        request.open('POST', 'http://127.0.0.1:5000/save', true);
        request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
        // TODO: agro.yml is hard-coded ...
        request.send("filename=" + 'agro.yml' + '&code=' + encodeURIComponent(code))
      }
    }
  });
};
