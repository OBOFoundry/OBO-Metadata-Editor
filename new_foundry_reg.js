let toggleInputRequired = ( checkbox, input ) => {
    checkbox.addEventListener( 'change', e => {
        if ( document.getElementById("ontoLicense3").checked ) {
            input.setAttribute( 'required', 'required' );
        } else {
            input.removeAttribute( 'required' );
            input.required=false;
        }
    } );

    var event = new Event('change');
    checkbox.dispatchEvent(event);
}

// Need to listen for changes on all the checkboxes, not just the 'other' checkbox,
// as only one change event is fired when the selection is toggled between them.
toggleInputRequired( document.getElementById("ontoLicense3"), document.getElementById("ontoLicenseTxt") );
toggleInputRequired( document.getElementById("ontoLicense1"), document.getElementById("ontoLicenseTxt") );
toggleInputRequired( document.getElementById("ontoLicense2"), document.getElementById("ontoLicenseTxt") );

document.getElementById("ontoLicenseTxt").addEventListener( 'change' , e => {
    const value = e.currentTarget.value.trim()
    if (value) {
        document.getElementById("ontoLicense3").checked = true;
        document.getElementById("ontoLicense3").value = value;
    }
})

document.getElementById("ontoLoc").addEventListener( 'change' , e => {
    const value = e.currentTarget.value.trim()
    if (value) {
        if (document.getElementById("issueTracker").value.length == 0) { //if not filled
           var url_pattern = /^https?:\/\/(w{3}\.)?github.com\/?/ ;
           if( value.match(url_pattern)) {
               document.getElementById("issueTracker").value = value+'/issues/';
           }
        }
    }
});