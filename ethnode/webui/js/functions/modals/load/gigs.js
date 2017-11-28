function loadGigs() {
    $.ajax({
        type: 'GET',
        url: '/api/v1/my/gigs/',
        dataType: 'text',
        success: function(data) {
            var gigIDS = JSON.parse(data);

            for(i = 0; i < 20; i++) {
                createGig(gigIDS[i]);
            }
        }
    });
}

loadGigs();