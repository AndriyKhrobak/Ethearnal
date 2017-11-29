// Loads more gigs on scroll down
var timesLoadedScrollDown = 0;

$(window).scroll(function() {
    if($(window).scrollTop() == $(document).height() - $(window).height()) {

        // FORMATING SEARCH QUERY
        formatSearchQuery();

        if (searchQuery == "/api/v1/my/idx/query/guids/?") {
            loadGigs();
            return false;
        }

        $.ajax({
            url: searchQuery,
            type: "GET",
            processData: false,
            success: function(data) {
                var gigIDS = JSON.parse(data);
                var gigsToLoad = 10;
                $gigsLoaded = $('.gig').length;

                var timesLoadAfter = (timesLoaded * gigsToLoad) + gigsToLoad;

                // LOADING MORE GIGS
                for(i = $gigsLoaded; i < timesLoadAfter; i++) {
                    createGig(gigIDS[i]);
                }

                timesLoadedScrollDown++;
            },
            error: function(error) {
                console.log('error! Search Query has not succeeded and has not been executed. Please contact support!')
            }
        });
    }
});