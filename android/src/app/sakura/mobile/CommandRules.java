package app.sakura.mobile;
import java.util.Locale;
import java.util.regex.*;
final class CommandRules {
 static String normalize(String input){return input.toLowerCase(Locale.ROOT).replace('’','\'').trim().replaceAll("[?!.,]+$","").replaceAll("\\s+"," ").replaceFirst("^(?:(?:can|could|would|will) you (?:please )?|please )","").replaceFirst(" please$","");}
 static boolean time(String t){return t.matches("(?:what(?:'s| is) (?:the )?(?:current )?time(?: is it)?|what time is it|tell me (?:the )?(?:current )?time|(?:current )?time(?: now)?)");}
 static boolean date(String t){return t.matches("(?:what(?:'s| is) (?:the |today's )?date(?: today)?|what day is (?:it|today)|tell me (?:the )?date|(?:today's |current )?date)");}
 static String number(String text){String t=text;String[] small={"zero","one","two","three","four","five","six","seven","eight","nine","ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"};String[] tens={"twenty","thirty","forty","fifty","sixty"};for(int i=0;i<tens.length;i++)for(int j=1;j<=9;j++)t=t.replaceAll("\\b"+tens[i]+"[ -]"+small[j]+"\\b",String.valueOf((i+2)*10+j));for(int i=0;i<tens.length;i++)t=t.replaceAll("\\b"+tens[i]+"\\b",String.valueOf((i+2)*10));for(int i=0;i<small.length;i++)t=t.replaceAll("\\b"+small[i]+"\\b",String.valueOf(i));return t;}
 static Matcher timer(String t){return Pattern.compile("(?:set|make|start) (?:a )?(?:timer (?:for )?)?(\\d{1,4})[ -]*(second|minute|hour)s?(?: timer)?").matcher(number(t));}
 static Matcher alarm(String t){return Pattern.compile("(?:set|make) (?:an? )?alarm (?:for |at )?(\\d{1,2})(?::(\\d{2}))?\\s*(am|pm)?").matcher(number(t).replaceAll("\\ba\\.m\\.?","am").replaceAll("\\bp\\.m\\.?","pm"));}
 static boolean news(String t){return t.matches("(?s).*(?:\\bnews\\b|headlines|समाचार|खबर).*")&&!t.matches("(?s).*(?:what is news|define news|meaning of news|fake news means).*");}
}
