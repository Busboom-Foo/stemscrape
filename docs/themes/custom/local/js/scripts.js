(function ($, Drupal) {
  Drupal.behaviors.myBehavior = {
    attach: function (context, settings) {

      // http://cotswoldphoto.co.uk/bootstrap-float-to-top-button/

      $('body').append('<div id="toTop" title="Back to top"><i class="fa fa-angle-up"></i></div>');
      $(window).scroll(function () {
        if ($(this).scrollTop() != 0) {
          $('#toTop').fadeIn();
        } else {
          $('#toTop').fadeOut();
        }
      });
      $('#toTop').click(function(){
        $("html, body").animate({ scrollTop: 0 }, 600);
        return false;
      });

      $("header a.search, a.search-close").click(function(event) {
        event.preventDefault();
        $("#block-local-search").slideToggle();
        $("#block-local-search input.form-search").focus();
        $("body").toggleClass("search-expanded");
      });
        


      function checkPosition() {
          if (window.matchMedia('(min-width: 992px)').matches) {
              $('.col-md-4 .card, .col-md-6 .card').matchHeight();
          }
      }
      if ($('.col-md-4 .card, .col-md-6 .card').length) {
          checkPosition();
      }


    }
  };
    $( document ).ready(function() {
         $(".bef-exposed-form .form-type-checkbox label").each(function() {
            $(this).contents().eq(1).wrap('<span/>');
        });
         $(".bef-exposed-form .form-type-radio label").each(function() {
            $(this).contents().eq(1).wrap('<span/>');
        });
    });
    
})(jQuery, Drupal);

