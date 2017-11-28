$category = '';
$jobType = '';
$experienceLevel = '';
$budget = '';

// SEARCH QUERY MAIN FUNCTION
function searchQueryDo() {

    // Function variables
    $filter = $('.filters .filter');

    // Search variables
    $search = $('input#search-header').val().replace(/ /g,"%20").toLowerCase();
    $search == '' ? $search = '' : $search = 'title=' + $search;

    // SEARCH QUERY VARIABLES
    $categoryParent = $filter.parent().find('.filter.category');
    $categoryText = $categoryParent.find('.is-checked span.mdl-checkbox__label').text().replace(/ /g,"_").toLowerCase();

    $jobTypeParent = $filter.parent().find('.filter.job-type');
    $jobTypeText = $jobTypeParent.find('.is-checked span.mdl-checkbox__label').text().replace(/ /g,"_").toLowerCase();

    $experienceLevelParent = $filter.parent().find('.filter.experience-level');
    $experienceLevelText = $experienceLevelParent.find('.is-checked span.mdl-checkbox__label').text().replace(/ /g,"_").toLowerCase();

    $budgetParent = $filter.parent().find('.filter.budget');
    $budgetText = $budgetParent.find('.is-checked span.mdl-checkbox__label').text().replace(/ /g,"_").toLowerCase();

    if ($categoryText !== '') $category = '&category=' + $categoryText;
    if ($jobTypeText !== '') $jobType = '&job_type=' + $jobTypeText;
    if ($experienceLevelText !== '') $experienceLevel = '&experience_level=' + $experienceLevelText;
    if ($budgetText !== '') $budget = '&budget=' + $budgetText;


    // FORMING SEARCH QUERY
    var search = '/api/v1/my/idx/query/objects/?' + $search + $category + $jobType + $experienceLevel + $budget;
    var searchQuery = search.replace('/api/v1/my/idx/query/objects/?&', '/api/v1/my/idx/query/objects/?');
    if (searchQuery == "/api/v1/my/idx/query/objects/?title=" || searchQuery == "/api/v1/my/idx/query/objects/?" || searchQuery == false) {
        return false;
    }

    $.ajax({
        url: searchQuery,
        type: "GET",
        processData: false,
        success: function(result) {
            $result = JSON.parse(result);
            console.log($result.length);
            if (result == '' || result == null || $result.length == null) return false;

            $result = JSON.parse(result);
            $('.gig').remove();

            for(i = 0; i < $result.length; i++) {
                createGigBox($result[i]);
            }

            $('input#search-header, button#search-button').removeClass('wrong');
            $filter.children().stop(true, true).removeClass('is-wrong');
        },
        error: function(error) {
            $('.gig').remove();
            $filter.find('.is-checked').stop(true, true).addClass('is-wrong');
            $('input#search-header, button#search-button').addClass('wrong');
        }
    });

    // null every filter
    $category = ''; $jobType = ''; $experienceLevel = ''; $budget = '';
}



// Search query based on filters
$('label.mdl-checkbox').click(function(e) {
    e.preventDefault();
    $label = $(this);
    $labelParent = $(this).parent();

    // IF USER UNSELECTS THE FILTER, THEN THIS HAPPENS
    if ($(this).hasClass('is-checked')) {
        $(this).stop(true, true).removeClass('is-checked is-wrong');

        searchQueryDo();

        return false;
    }


    // Making sure you can select only one checkbox per filter
    $labelParent.find('.is-checked').not($(this)).stop(true, true).removeClass('is-checked is-wrong');
    $(this).stop(true, true).toggleClass('is-checked');

    searchQueryDo();
});

// Also a search query based on filters, but this function works only when you click on a button that's right next to search input
$('button#search-button').click(function(e) {
    e.preventDefault();
    searchQueryDo();
})

// When you press enter while in search box input, it will run search query function too.
$('input#search-header').keypress(function (e) {
    if (e.which == 13) {
        e.preventDefault();

        searchQueryDo();

        return false;
    }
});