/**
 * Gets the document element corresponding to the "commit" button. This will be variable depending
 * on whether the editor is being used to update an existing or add a new config file.
 */
var get_commit_btn = function() {
  if (document.getElementById("update-btn")) {
    return document.getElementById("update-btn");
  }
  else {
    return document.getElementById("add-btn");
  }
}

/**
 * Shows or hides an element of text when a link is clicked
 */
function showHideText(elemToShow, elemToHide) {
    // show this element
    document.getElementById(elemToShow).style.display = 'inherit';
    // hide this element
    document.getElementById(elemToHide).style.display = 'none';
}

/**
 * Formats a String message as a dismissable Bootstrap alert text.
 * For example, passing parameter style = alert-danger gives a red box.
 */
function showAlertFor(text, style, extraText='') {
    $("#status-area").removeClass()
    $("#status-area").show()
    $("#status-area").addClass("alert "+style+" alert-dismissable fade show");
    $("#alert-message").html(text);

    if ( extraText.length > 0) {
        $("#details-area").show();
        $("#detail-message").html(extraText);
    } else {
        $("#detail-message").text(extraText);
        $("#details-area").hide();
    }

    $(".alert").alert()

    $("#close-alert-btn").click(function() {
        $("#alert-message").text('');
        $(this).parent().hide();
    });
}

/**
 * Handler to allow search of the ontologies table
 */
$(document).ready(function(){
  $("#table-search").val('');
  $("#table-search").on("keyup", function() {
    var value = $(this).val().toLowerCase();
    doTableSearch(value)
  });
});

/**
 * Applies a particular search value to filter the ontologies table
 */
function doTableSearch(searchVal) {
    $("#tb-ontologies tr").filter(function() {
      $(this).toggle($(this).text().toLowerCase().indexOf(searchVal) > -1)
    });
    var rowCount = $('#tb-ontologies tr:visible').length;
    $("#search-result-count").text(rowCount+" rows");
}

/**
 * Removes any applied search filters from the ontologies table
 */
function clearTableSearch() {
    $("#table-search").val('');
    doTableSearch('');
}


/**
 * Initialize the editor instance if the element with the id "code" exists.
 */
var editor;
if (document.getElementById("code")) {
  editor = CodeMirror.fromTextArea(document.getElementById("code"), {
    /* Instantiates a CodeMirror editor object from the HTML text area called "code" */
    mode: "text/x-yaml",
    theme: "default",
    lineNumbers: true,
    matchBrackets: true,
    showCursorWhenSelecting: true,
    extraKeys: {
      "F11": function(cm) {
        // If F11 is pressed and we are not already in fullscreen mode, pop up a dialog informing the
        // user how to get out of it:
        if (!cm.getOption("fullScreen")) {
          bootbox.alert({
            title: 'Entering fullscreen editor mode',
            message: 'To leave fullscreen mode, press F11 or Esc',
            closeButton: false,
          });
        }
        // Toggle fullscreen mode:
        cm.setOption("fullScreen", !cm.getOption("fullScreen"));
      },
      "Esc": function(cm) {
        // Pressing escape leaves fullscreen mode if we are currently in it:
        if (cm.getOption("fullScreen"))
          cm.setOption("fullScreen", false);
      },
      Tab: function(cm) {
        // Pressing the tab key actually produces spaces, not tabs:
        var spaces = Array(cm.getOption("indentUnit") + 1).join(" ");
        cm.replaceSelection(spaces);
      },
    }
  });


  /**
   * Add our custom hinting function to the editor
   */
  CodeMirror.commands.autocomplete = function(cm) {
    cm.showHint({hint: purlYamlHint, completeSingle: false});
  }


  /**
   * Activate hint popup on any letter key press
   */
  editor.on("keyup", function (cm, event) {
    // If the autocompletion popup is not already active, and if the user has typed a letter,
    // then activate the autocompletion popup:
    if (!cm.state.completionActive) {
      // Letter keys only:
      keyPressed = event.key.toLowerCase();
      if (keyPressed === ':' || keyPressed === '/' || (keyPressed >= 'a' && keyPressed <= 'z')) {
        CodeMirror.commands.autocomplete(cm);
      }
    }
  });


  /**
   * Disable the pr button when the contents of the editor are changed, and make sure the cursor
   * stays in view. The latter is important because sometimes autocomplete will insert multiple
   * lines into the editor.
   */
  editor.on("changes", function() {
    get_commit_btn().disabled = true;
    editor.scrollIntoView(what={line: editor.getCursor().line, ch: 0}, margin=12);
  });


  /**
   * Disable the commit button if the user refreshes or otherwise leaves the page,
   * and ask the user to confirm.
   */
  window.onbeforeunload = function() {
    get_commit_btn().disabled = true;
    return "Do you really want to leave this page? Your edits will not be saved.";
  }
}


/**
 * Generates completion hints depending on the current cursor position of the yaml file
 */
var purlYamlHint = function(editor, options) {
  var cursor = editor.getCursor();
  var thisLine = editor.getLine(cursor.line);
  var currEnd = cursor.ch;
  var currStart = currEnd;

  // Look left and right from the current cursor position to have in view the entire word at that
  // location:
  while (currStart && /[:\/\w]+/.test(thisLine.charAt(currStart - 1))) {
    --currStart;
  }
  while (currEnd && /[:\/\w]+/.test(thisLine.charAt(currEnd))) {
    ++currEnd;
  }
  var currWord = thisLine.slice(currStart, currEnd);

  var getContext = function() {
    /* Finds the nearest root-level directive above the current line (if one exists) and returns its
       name. */
    var lineNum = cursor.line;
    var matches = /^(\w+):/.exec(editor.getLine(lineNum));
    while (!matches && lineNum > 0) {
      matches = /^(\w+):/.exec(editor.getLine(--lineNum));
    }
    return matches && matches[1];
  };

  // The beginning and ending positions of the text that will be replaced if a completion
  // hint is selected:
  var from = CodeMirror.Pos(cursor.line, currStart);
  var to = CodeMirror.Pos(cursor.line, currEnd);

  // If there is no word here just return an empty list:
  if (currStart === currEnd) {
    return {list: [], from: from, to: to}
  }

  var pruneReplacementList = function(replacementList) {
    /* Prunes the given list of completions to only those which begin with the current word.
       If none match, then returns the entire list.
       If there is only one match and it is exact, return nothing.  */
    prunedList = replacementList.filter(function(r) {
      return (new RegExp("^" + currWord).test(r['displayText']));
    });
    if (!prunedList || prunedList.length === 0) {
      return replacementList;
    }
    else if (prunedList.length === 1 && prunedList[0]['displayText'] === currWord) {
      return [];
    }
    else {
      return prunedList;
    }
  };

  // Send back a completion hint list contextualised to the current position as well as to
  // the letters that have been typed so far.
  var prevString = thisLine.slice(0, currStart);
  var context = getContext();
  if (prevString === '') {
    return {list: pruneReplacementList([{displayText: 'base_redirect:', text: 'base_redirect: '},
                                        {displayText: 'base_url:', text: 'base_url: '},
                                        {displayText: 'entries:', text: 'entries:\n- '},
                                        {displayText: 'example_terms:', text: 'example_terms:\n- '},
                                        {displayText: 'idspace:', text: 'idspace: '},
                                        {displayText: 'products:', text: 'products:\n- '},
                                        {displayText: 'term_browser:', text: 'term_browser: '},
                                        {displayText: 'tests:', text: 'tests:\n- from: \n  to: '}]),
            from: from, to: to};
  }
  else if (/^term_browser:\s+$/.test(prevString)) {
    return {list: pruneReplacementList([{displayText: 'ontobee', text: 'ontobee'},
                                        {displayText: 'custom', text: 'custom'}]),
            from: from, to: to};
  }
  else if (/^base_url:\s+$/.test(prevString) && !(/^\/obo\//.test(currWord))) {
    return {list: pruneReplacementList([{displayText: '/obo/', text: '/obo/'}]),
            from: from, to: to};
  }
  else if (/^-\s+$/.test(prevString) && context === 'tests') {
    return {list: pruneReplacementList([{displayText: 'from:', text: 'from: \n  to: '},
                                        {displayText: 'to:', text: 'to: '}]),
            from: from, to: to};
  }
  else if (/^\s*-\s+from:\s+$/.test(prevString) && (context === 'tests' || context === 'entries') &&
           !(/^\//.test(currWord))) {
    return {list: pruneReplacementList([{displayText: '/', text: '/'}]),
            from: from, to: to};
  }
  else if (/^\s+to:\s+$/.test(prevString) && (context === 'tests' || context === 'entries') &&
           !(/^(https?|ftp):\/\//.test(currWord))) {
    return {list: pruneReplacementList([{displayText: 'http://', text: 'http://'},
                                        {displayText: 'https://', text: 'https://'},
                                        {displayText: 'ftp://', text: 'ftp://'},]),
            from: from, to: to};
  }
  else if (/^-\s+$/.test(prevString) && context === 'entries') {
    return {list: pruneReplacementList([{displayText: 'exact:', text: 'exact: \n  replacement: '},
                                        {displayText: 'prefix:', text: 'prefix: \n  replacement: '},
                                        {displayText: 'regex:', text: 'regex: \n  replacement: '}]),
            from: from, to: to};
  }
  else if (prevString === '  ' && context === 'entries') {
    return {list: pruneReplacementList([{displayText: 'replacement:', text: 'replacement: '},
                                        {displayText: 'status:', text: 'status: '},
                                        {displayText: 'tests:', text: 'tests:\n  - from: \n    to: '}]),
            from: from, to: to};
  }
  else if (/^-\s+(exact|prefix):\s+$/.test(prevString) && context === 'entries' &&
           !(/^\//.test(currWord))) {
    return {list: pruneReplacementList([{displayText: '/', text: '/'}]),
            from: from, to: to};
  }
  else if (/^\s+replacement:\s+$/.test(prevString) && context === 'entries' &&
           !(/^(https?|ftp):\/\//.test(currWord))) {
    return {list: pruneReplacementList([{displayText: 'http://', text: 'http://'},
                                        {displayText: 'https://', text: 'https://'},
                                        {displayText: 'ftp://', text: 'ftp://'},]),
            from: from, to: to};
  }
  else if (/^\s+status:\s+$/.test(prevString) && context === 'entries' &&
           !(/^(permanent|temporary|see other):\/\//.test(currWord))) {
    return {list: pruneReplacementList([{displayText: 'permanent', text: 'permanent'},
                                        {displayText: 'temporary', text: 'temporary'},
                                        {displayText: 'see other', text: 'see other'}]),
            from: from, to: to};
  }
};

/**
 * Validates the contents of the editor, displaying the validation result in the status area.
 */
var validate = function(filename) {
  // Save the contents of the editor to its associated text area:
  editor.save();

  // Extract the code from the text area:
  var code = document.getElementById("code").value;

  // Clear the status area:
  showAlertFor("Validating ...", "alert-info") ;

  // Before doing anything else, make sure that the idspace indicated in the code matches the
  // idspace being edited:
  var expected_idspace = filename.toUpperCase().replace(".YML", "");
  var actual_idspace = code.match(/[^\S\r\n]*idspace:[^\S\r\n]+(.+?)[^\S\r\n]*\n/m);
  if (!actual_idspace) {
    showAlertFor("Validation failed: \'idspace: \' is required", "alert-danger") ;
    get_commit_btn().disabled = true;
    return;
  }
  else if (actual_idspace[1] !== expected_idspace) {
    showAlertFor("Validation failed: \'idspace: " + actual_idspace[1] +
      "\' does not match expected idspace: \'" + expected_idspace + "\'", "alert-danger")  ;
    get_commit_btn().disabled = true;
    return;
  }

  // Embed the code into a POST request and send it to the server for processing.
  // If the validation is successful, enable the Pr button, otherwise disable it.
  var request = new XMLHttpRequest();
  request.onreadystatechange = function() {
    $("*").css("cursor", "default");
    if (request.readyState === 4) {
      if (!request.status) {
        showAlertFor("Problem communicating with server","alert-danger");
        get_commit_btn().disabled = true;
      }
      else if (request.status === 200) {
        showAlertFor("Validation successful", "alert-success") ;
        get_commit_btn().disabled = false;
      }
      else {
        // Display the error message in the status area. Note that we must replace any angle
        // angle brackets with HTML escape codes.
        var response = JSON.parse(request.responseText);
        alertText = 'Validation failed';
        alertText += response.line_number >= 0 ? ('. At line ' + response.line_number + ': ') : ': ';
        alertText += response.summary + '\n';
        alertText = alertText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        alertTextDetail = response.details + '\n';
        alertTextDetail = alertTextDetail.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        showAlertFor(alertText,"alert-danger",alertTextDetail);
        get_commit_btn().disabled = true;
        // If the line number is valid, then add it to the message and highlight that line in the
        // editor while scrolling it into view.
        if (response.line_number >= 0) {
          var marker = editor.markText({line: response.line_number - 1, ch: 0},
                                       {line: response.line_number, ch: 0},
                                       {className: "line-error", clearOnEnter: true});

          editor.scrollIntoView(what={line: response.line_number, ch: 0}, margin=32);

          // Clear the highlighting after 5000ms:
          setTimeout(function() {
            marker.clear();
          }, 5000);

        }
      }
    }
  }
  request.open('POST', '/validate', true);
  request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  request.send("code=" + encodeURIComponent(code));
  $("*").css("cursor", "progress");
};


/**
 * Submit a pull request to github to add a new configuration to the repository.
 */
var add_config = function(filename) {
  // Get a confirmation from the user:
  bootbox.prompt({
    title: "Please describe the new configuration you would like to add: " +
      filename.toUpperCase().replace(".YML", ""),
    inputType: 'textarea',
    value: 'Adding ' + filename,
    buttons: {
      confirm: {
        label: 'Submit',
        className: 'btn-danger'
      },
      cancel: {
        label: 'Cancel',
        className: 'btn-primary'
      }
    },
    callback: function(commit_msg) {
      if (commit_msg !== null && commit_msg !== undefined) {
        if (!commit_msg || commit_msg.trim() === "") {
          bootbox.alert({
            closeButton: false,
            message: "Commit message cannot be empty. New configuration was not submitted."});
          return;
        }

        // Disable the add button:
        get_commit_btn().disabled = true;

        // Extract the code from the text area:
        var code = document.getElementById("code").value;

        showAlertFor("Submitting new configuration ...","alert-info");

        // Embed the code into a request.
        var request = new XMLHttpRequest();
        // Define a function to handle a state change of the request:
        request.onreadystatechange = function() {
          $("*").css("cursor", "default");
          if (request.readyState === 4) {
            if (!request.status) {
              showAlertFor("Problem communicating with server","alert-danger");
            }
            else if (request.status === 200) {
              var response = JSON.parse(request.responseText);
              var prInfo = response['pr_info'];
              showAlertFor('New configuration submitted successfully. It will be ' +
                'reviewed by a moderator before being added to the repository. Click ' +
                '<a href="' + prInfo['html_url'] + '" target="__blank">here</a> to view your ' +
                'pull request on GitHub.',"alert-success");
            }
            else {
              // Display the error message in the status area. Note that we must replace any angle
              // angle brackets with HTML escape codes.
              alertText = "Submission of new configuration failed.\n\n" +
                request.responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
              showAlertFor(alertText,"alert-danger");
            }
          }
        }
        // Post the request to the server.
        request.open('POST', '/add_config', true);
        request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
        request.send('filename=' + filename +
                     '&commit_msg=' + commit_msg +
                     '&code=' + encodeURIComponent(code))
        $("*").css("cursor", "progress");
      }
    }
  });
}


/**
 * Submit a pull request to github to update the given configuration file in the repository.
 */
var update_config = function(filename) {
  // Get a confirmation from the user:
  bootbox.prompt({
    title: "Please describe the changes you have made to " +
      filename.toUpperCase().replace(".YML", ""),
    inputType: 'textarea',
    value: 'Updating ' + filename,
    buttons: {
      confirm: {
        label: 'Submit',
        className: 'btn-danger'
      },
      cancel: {
        label: 'Cancel',
        className: 'btn-primary'
      }
    },
    callback: function(commit_msg) {
      if (commit_msg !== null && commit_msg !== undefined) {
        if (!commit_msg || commit_msg.trim() === "") {
          bootbox.alert({
            closeButton: false,
            message: "Commit message cannot be empty. Your change has not been submitted."});
          return;
        }

        // Disable the update button:
        get_commit_btn().disabled = true;

        // Extract the code from the text area:
        var code = document.getElementById("code").value;

        showAlertFor("Submitting update ...","alert-info");

        // Embed the code into a request.
        var request = new XMLHttpRequest();
        // Define a function to handle a state change of the request:
        request.onreadystatechange = function() {
          $("*").css("cursor", "default");
          if (request.readyState === 4) {
            if (!request.status) {
              showAlertFor("Problem communicating with server","alert-danger");
            }
            else if (request.status === 200) {
              var response = JSON.parse(request.responseText);
              var prInfo = response['pr_info'];
              showAlertFor('Update submitted successfully. The changes will be ' +
                'reviewed by a moderator before being added to the repository. Click ' +
                '<a href="' + prInfo['html_url'] + '" target="__blank">here</a> to view your ' +
                'pull request on GitHub.',"alert-success");
            }
            else {
              // Display the error message in the status area. Note that we must replace any angle
              // angle brackets with HTML escape codes.
              alertText = "Submission of update failed.\n\n" +
                request.responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
              showAlertFor(alertText,"alert-danger");
            }
          }
        }
        // Post the request to the server.
        request.open('POST', '/update_config', true);
        request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
        request.send('filename=' + filename +
                     '&commit_msg=' + commit_msg +
                     '&code=' + encodeURIComponent(code))
        $("*").css("cursor", "progress");
      }
    }
  });
};
